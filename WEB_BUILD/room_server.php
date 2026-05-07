<?php
declare(strict_types=1);

const PAN_TRIAL_MAX_ROOMS = 200;
const PAN_TRIAL_ROOM_TIMEOUT_SECONDS = 21600;
const PAN_TRIAL_MAX_STATE_BYTES = 5000000;
const PAN_TRIAL_MAX_PREGAME_FIELD_BYTES = 1200000;
const PAN_TRIAL_MAX_MESSAGE_BYTES = 280;

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Cache-Control: no-store');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

try {
    $result = with_room_lock(function (string $dataDir): array {
        cleanup_inactive_rooms($dataDir);
        return handle_request($dataDir);
    });
    respond_json($result['status'], $result['payload']);
} catch (Throwable $exc) {
    respond_json(400, ['error' => $exc->getMessage()]);
}

function handle_request(string $dataDir): array
{
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    $parts = request_parts();
    $body = read_json_body();

    if ($method === 'GET' && $parts === ['health']) {
        return ok([
            'ok' => true,
            'rooms' => active_room_count($dataDir),
            'max_rooms' => PAN_TRIAL_MAX_ROOMS,
            'room_timeout_seconds' => PAN_TRIAL_ROOM_TIMEOUT_SECONDS,
            'server_mode' => 'php_relay',
        ]);
    }

    if ($method === 'GET' && count($parts) === 2 && $parts[0] === 'rooms') {
        $room = load_room($dataDir, $parts[1]);
        touch_room($room);
        save_room($dataDir, $room);
        return ok(room_response($room));
    }

    if ($method === 'POST' && $parts === ['rooms']) {
        return create_room($dataDir, $body);
    }

    if ($method === 'POST' && count($parts) === 3 && $parts[0] === 'rooms') {
        $code = $parts[1];
        $action = $parts[2];
        if ($action === 'join') {
            return join_room($dataDir, $code, $body);
        }
        if ($action === 'ready') {
            return ready_room($dataDir, $code, $body);
        }
        if ($action === 'draft' || $action === 'actions') {
            return accept_client_snapshot($dataDir, $code, $body);
        }
        if ($action === 'rematch') {
            return request_rematch($dataDir, $code, $body);
        }
        if ($action === 'decline') {
            return decline_rematch($dataDir, $code, $body);
        }
        if ($action === 'leave') {
            return leave_room($dataDir, $code, $body);
        }
    }

    throw new RuntimeException('Unknown endpoint');
}

function create_room(string $dataDir, array $body): array
{
    if (active_room_count($dataDir) >= PAN_TRIAL_MAX_ROOMS) {
        throw new RuntimeException('Room server is full; try again later');
    }

    $code = generate_room_code($dataDir);
    $playerName = unique_player_name((string)($body['name'] ?? ''), 0, []);
    $playerToken = generate_player_token();
    $room = [
        'room_code' => $code,
        'players' => ['0' => $playerName],
        'player_tokens' => ['0' => $playerToken],
        'ready' => false,
        'ready_players' => [],
        'stage' => 'lobby',
        'revision' => 0,
        'message' => 'Waiting for another player.',
        'rematch_votes' => [],
        'rematch_declined' => false,
        'rematch_declined_by' => null,
        'rematch_declined_name' => '',
        'pregame' => clean_pregame(is_array($body['pregame'] ?? null) ? $body['pregame'] : []),
        'last_touched' => time(),
    ];
    save_room($dataDir, $room);
    return ok(room_response($room, 0));
}

function join_room(string $dataDir, string $code, array $body): array
{
    $room = load_room($dataDir, $code);
    touch_room($room);
    if (($room['stage'] ?? 'lobby') !== 'lobby') {
        throw new RuntimeException('Room has already started');
    }

    $players = normalized_players($room);
    $openSeats = array_values(array_diff([0, 1], array_map('intval', array_keys($players))));
    if (!$openSeats) {
        throw new RuntimeException('Room already has two players');
    }

    $playerId = $openSeats[0];
    $playerToken = generate_player_token();
    $players[(string)$playerId] = unique_player_name((string)($body['name'] ?? ''), $playerId, array_values($players));
    ksort($players);
    $room['players'] = $players;
    $playerTokens = is_array($room['player_tokens'] ?? null) ? $room['player_tokens'] : [];
    $playerTokens[(string)$playerId] = $playerToken;
    $room['player_tokens'] = $playerTokens;
    $room['ready'] = count($players) >= 2;
    $room['message'] = 'Both players connected. Press Ready when you are both looking at this screen.';
    $room['revision'] = intval($room['revision'] ?? 0) + 1;
    save_room($dataDir, $room);
    return ok(room_response($room, $playerId));
}

function ready_room(string $dataDir, string $code, array $body): array
{
    $room = load_room($dataDir, $code);
    touch_room($room);
    $playerId = require_player_token($room, $body);
    $players = normalized_players($room);
    if (count($players) < 2) {
        throw new RuntimeException('Room is waiting for another player');
    }
    if (($room['stage'] ?? 'lobby') !== 'lobby') {
        save_room($dataDir, $room);
        return ok(room_response($room, $playerId));
    }

    $readyPlayers = normalized_int_list($room['ready_players'] ?? []);
    if (!in_array($playerId, $readyPlayers, true)) {
        $readyPlayers[] = $playerId;
        sort($readyPlayers);
    }
    $room['ready_players'] = $readyPlayers;
    $room['ready'] = true;
    if (in_array(0, $readyPlayers, true) && in_array(1, $readyPlayers, true)) {
        $room['stage'] = 'coin_flip';
        $room['message'] = 'Both players are ready. Starting the coin flip.';
    } else {
        $room['message'] = ($players[(string)$playerId] ?? 'Player') . ' is ready. Waiting for the other player.';
    }
    $room['revision'] = intval($room['revision'] ?? 0) + 1;
    save_room($dataDir, $room);
    return ok(room_response($room, $playerId));
}

function accept_client_snapshot(string $dataDir, string $code, array $body): array
{
    $room = load_room($dataDir, $code);
    touch_room($room);
    $playerId = require_player_token($room, $body);
    assert_revision($room, $body);
    $snapshot = $body['snapshot'] ?? null;
    if (!is_array($snapshot)) {
        throw new RuntimeException('Missing room snapshot');
    }

    $endpoint = request_parts()[2] ?? '';
    assert_snapshot_is_allowed($room, $snapshot, $endpoint, $body, $playerId);
    $room = merge_client_snapshot($room, $snapshot);
    $room['revision'] = intval($body['revision'] ?? ($room['revision'] ?? 0)) + 1;
    touch_room($room);
    save_room($dataDir, $room);
    return ok(room_response($room, $playerId));
}

function request_rematch(string $dataDir, string $code, array $body): array
{
    $room = load_room($dataDir, $code);
    touch_room($room);
    $playerId = require_player_token($room, $body);
    $players = normalized_players($room);
    if (!empty($room['rematch_declined'])) {
        save_room($dataDir, $room);
        return ok(room_response($room, $playerId));
    }

    $votes = normalized_int_list($room['rematch_votes'] ?? []);
    if (!in_array($playerId, $votes, true)) {
        $votes[] = $playerId;
        sort($votes);
    }

    if (count($players) >= 2 && in_array(0, $votes, true) && in_array(1, $votes, true)) {
        $room['stage'] = 'coin_flip';
        $room['state'] = null;
        unset($room['state']);
        $room['ready'] = true;
        $room['ready_players'] = [0, 1];
        $room['pregame'] = clean_pregame(is_array($body['pregame'] ?? null) ? $body['pregame'] : []);
        $room['message'] = 'Both players chose Play Again. Starting a new coin flip.';
        $room['rematch_votes'] = [];
        $room['rematch_declined'] = false;
        $room['rematch_declined_by'] = null;
        $room['rematch_declined_name'] = '';
    } else {
        $room['rematch_votes'] = $votes;
        $room['message'] = ($players[(string)$playerId] ?? 'Player') . ' would like to play again.';
    }
    $room['revision'] = intval($room['revision'] ?? 0) + 1;
    save_room($dataDir, $room);
    return ok(room_response($room, $playerId));
}

function decline_rematch(string $dataDir, string $code, array $body): array
{
    $room = load_room($dataDir, $code);
    touch_room($room);
    $playerId = require_player_token($room, $body);
    $players = normalized_players($room);
    mark_rematch_declined($room, $playerId, $players[(string)$playerId]);
    $room['revision'] = intval($room['revision'] ?? 0) + 1;
    save_room($dataDir, $room);
    return ok(room_response($room, $playerId));
}

function leave_room(string $dataDir, string $code, array $body): array
{
    $room = load_room($dataDir, $code);
    touch_room($room);
    $playerId = require_player_token($room, $body);
    $players = normalized_players($room);
    if (array_key_exists((string)$playerId, $players)) {
        $departedName = $players[(string)$playerId];
        unset($players[(string)$playerId]);
        if (is_array($room['player_tokens'] ?? null)) {
            unset($room['player_tokens'][(string)$playerId]);
        }
        if (!$players) {
            @unlink(room_path($dataDir, $code));
            return ok(['left' => true, 'room_closed' => true, 'server_mode' => 'php_relay']);
        }

        if (($room['stage'] ?? '') === 'game' && empty($room['rematch_declined'])) {
            mark_rematch_declined($room, $playerId, $departedName);
        }
        $room['players'] = $players;
        $room['ready'] = count($players) >= 2;
        $room['ready_players'] = array_values(array_filter(
            normalized_int_list($room['ready_players'] ?? []),
            function (int $readyPlayerId) use ($playerId): bool {
                return $readyPlayerId !== $playerId;
            }
        ));
        $room['message'] = $departedName . ' left the room.';
        $room['revision'] = intval($room['revision'] ?? 0) + 1;
    }
    save_room($dataDir, $room);
    return ok(room_response($room));
}

function merge_client_snapshot(array $room, array $snapshot): array
{
    $merged = $room;
    $merged['stage'] = clean_stage((string)($snapshot['stage'] ?? ($room['stage'] ?? 'lobby')));
    $merged['message'] = clean_message((string)($snapshot['message'] ?? ($room['message'] ?? '')));
    $merged['pregame'] = clean_pregame(is_array($snapshot['pregame'] ?? null) ? $snapshot['pregame'] : ($room['pregame'] ?? []));
    $merged['rematch_votes'] = normalized_int_list($snapshot['rematch_votes'] ?? ($room['rematch_votes'] ?? []));
    $merged['rematch_declined'] = !empty($snapshot['rematch_declined']);
    $merged['rematch_declined_by'] = isset($snapshot['rematch_declined_by']) ? intval($snapshot['rematch_declined_by']) : null;
    $merged['rematch_declined_name'] = clean_message((string)($snapshot['rematch_declined_name'] ?? ''));
    if (isset($snapshot['state']) && is_string($snapshot['state']) && $snapshot['state'] !== '') {
        $merged['state'] = clean_payload_string($snapshot['state'], PAN_TRIAL_MAX_STATE_BYTES, 'state');
    } else {
        unset($merged['state']);
    }
    return $merged;
}

function room_response(array $room, ?int $playerId = null): array
{
    $response = [
        'room_code' => (string)($room['room_code'] ?? ''),
        'players' => normalized_players($room),
        'ready' => !empty($room['ready']),
        'ready_players' => normalized_int_list($room['ready_players'] ?? []),
        'stage' => clean_stage((string)($room['stage'] ?? 'lobby')),
        'revision' => intval($room['revision'] ?? 0),
        'message' => (string)($room['message'] ?? ''),
        'rematch_votes' => normalized_int_list($room['rematch_votes'] ?? []),
        'rematch_declined' => !empty($room['rematch_declined']),
        'rematch_declined_by' => isset($room['rematch_declined_by']) ? $room['rematch_declined_by'] : null,
        'rematch_declined_name' => (string)($room['rematch_declined_name'] ?? ''),
        'pregame' => is_array($room['pregame'] ?? null) ? $room['pregame'] : [],
        'server_mode' => 'php_relay',
    ];
    if ($playerId !== null) {
        $response['player_id'] = $playerId;
        $tokens = is_array($room['player_tokens'] ?? null) ? $room['player_tokens'] : [];
        if (isset($tokens[(string)$playerId])) {
            $response['player_token'] = (string)$tokens[(string)$playerId];
        }
    }
    if (isset($room['state']) && is_string($room['state']) && $room['state'] !== '') {
        $response['state'] = $room['state'];
    }
    return $response;
}

function mark_rematch_declined(array &$room, int $playerId, string $playerName): void
{
    $room['rematch_votes'] = [];
    $room['rematch_declined'] = true;
    $room['rematch_declined_by'] = $playerId;
    $room['rematch_declined_name'] = $playerName;
    $room['message'] = $playerName . ' returned to the main menu.';
}

function require_player_token(array $room, array $body): int
{
    $playerId = intval($body['player_id'] ?? -1);
    $players = normalized_players($room);
    if (!array_key_exists((string)$playerId, $players)) {
        throw new RuntimeException('Player is not in this room');
    }

    $tokens = is_array($room['player_tokens'] ?? null) ? $room['player_tokens'] : [];
    $expected = (string)($tokens[(string)$playerId] ?? '');
    $provided = (string)($body['player_token'] ?? '');
    if ($expected === '' || $provided === '' || !hash_equals($expected, $provided)) {
        throw new RuntimeException('Player token did not match; recreate or rejoin the room');
    }
    return $playerId;
}

function assert_snapshot_is_allowed(
    array $room,
    array $snapshot,
    string $endpoint,
    array $body,
    int $playerId
): void {
    $currentStage = clean_stage((string)($room['stage'] ?? 'lobby'));
    $nextStage = clean_stage((string)($snapshot['stage'] ?? $currentStage));

    if ($endpoint === 'draft') {
        if (!in_array($currentStage, ['coin_flip', 'draft'], true)) {
            throw new RuntimeException('The draft is not active');
        }
        if (!in_array($nextStage, ['draft', 'game'], true)) {
            throw new RuntimeException('Draft snapshots may only continue the draft or start the game');
        }
        if (!isset($body['card_index']) || intval($body['card_index']) < 0 || intval($body['card_index']) > 11) {
            throw new RuntimeException('Draft card is out of range');
        }
        if ($nextStage === 'game' && empty($snapshot['state'])) {
            throw new RuntimeException('Draft-complete snapshot is missing game state');
        }
        return;
    }

    if ($endpoint === 'actions') {
        if ($currentStage !== 'game') {
            throw new RuntimeException('Game has not started yet');
        }
        if ($nextStage !== 'game') {
            throw new RuntimeException('Gameplay snapshots must stay in the game stage');
        }
        if (intval($body['action_player_id'] ?? -1) !== $playerId) {
            throw new RuntimeException('Submitted action does not belong to this player');
        }
        $allowedActionTypes = [
            'move',
            'pick_up_current',
            'play_card',
            'choose_combat_card',
            'choose_request',
            'select_damage_card',
            'select_restructure_suit',
            'select_plane_shift_direction',
            'resolve_plane_shift',
            'resolve_ballista_shot',
            'cancel_request_selection',
            'place_cards',
        ];
        if (!in_array((string)($body['action_type'] ?? ''), $allowedActionTypes, true)) {
            throw new RuntimeException('Unknown action type');
        }
        if (empty($snapshot['state'])) {
            throw new RuntimeException('Gameplay snapshot is missing game state');
        }
        return;
    }

    throw new RuntimeException('Unknown room snapshot endpoint');
}

function assert_revision(array $room, array $body): void
{
    if (!array_key_exists('revision', $body)) {
        return;
    }
    if (intval($body['revision']) !== intval($room['revision'] ?? 0)) {
        throw new RuntimeException('Room state changed; refresh and try again');
    }
}

function generate_player_token(): string
{
    return bin2hex(random_bytes(24));
}

function clean_message(string $message): string
{
    return substr(trim(preg_replace('/\s+/', ' ', $message)), 0, PAN_TRIAL_MAX_MESSAGE_BYTES);
}

function clean_payload_string(string $payload, int $maxBytes, string $field): string
{
    if (strlen($payload) > $maxBytes) {
        throw new RuntimeException($field . ' payload is too large');
    }
    if (!preg_match('/^[A-Za-z0-9+\/=]*$/', $payload)) {
        throw new RuntimeException($field . ' payload is not valid base64 text');
    }
    return $payload;
}

function clean_pregame(array $pregame): array
{
    $stringFields = [
        'labyrinth_cards',
        'draft_cards',
        'available_cards',
        'jack_cards',
        'jack_order',
        'draft_hands',
        'player_cards',
    ];
    $cleaned = [];
    foreach ($stringFields as $field) {
        if (isset($pregame[$field]) && is_string($pregame[$field])) {
            $cleaned[$field] = clean_payload_string($pregame[$field], PAN_TRIAL_MAX_PREGAME_FIELD_BYTES, $field);
        }
    }
    foreach (['draft_starting_player', 'current_drafter'] as $field) {
        if (isset($pregame[$field])) {
            $cleaned[$field] = max(0, min(1, intval($pregame[$field])));
        }
    }
    if (isset($pregame['kings_drafted'])) {
        $cleaned['kings_drafted'] = max(0, min(2, intval($pregame['kings_drafted'])));
    }
    return $cleaned;
}

function unique_player_name(string $playerName, int $playerId, array $existingNames): string
{
    $name = trim(preg_replace('/\s+/', ' ', $playerName)) ?: 'Player ' . ($playerId + 1);
    $existing = array_map(function (string $value): string {
        return strtolower(trim($value));
    }, $existingNames);
    if (!in_array(strtolower($name), $existing, true)) {
        return $name;
    }

    $suffix = 1;
    do {
        $candidate = $name . $suffix;
        $suffix++;
    } while (in_array(strtolower($candidate), $existing, true));
    return $candidate;
}

function clean_stage(string $stage): string
{
    return in_array($stage, ['lobby', 'coin_flip', 'draft', 'game'], true) ? $stage : 'lobby';
}

function normalized_players(array $room): array
{
    $players = is_array($room['players'] ?? null) ? $room['players'] : [];
    $normalized = [];
    foreach ($players as $key => $value) {
        $playerId = (string)intval($key);
        if ($playerId === '0' || $playerId === '1') {
            $normalized[$playerId] = (string)$value;
        }
    }
    ksort($normalized);
    return $normalized;
}

function normalized_int_list($value): array
{
    if (!is_array($value)) {
        return [];
    }
    $result = [];
    foreach ($value as $item) {
        $number = intval($item);
        if (($number === 0 || $number === 1) && !in_array($number, $result, true)) {
            $result[] = $number;
        }
    }
    sort($result);
    return $result;
}

function read_json_body(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || trim($raw) === '') {
        return [];
    }
    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        throw new RuntimeException('Request body must be JSON');
    }
    return $decoded;
}

function request_parts(): array
{
    $path = (string)($_GET['path'] ?? '');
    if ($path === '') {
        $path = (string)($_SERVER['PATH_INFO'] ?? '');
    }
    if ($path === '') {
        $requestPath = parse_url((string)($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH) ?: '/';
        $scriptName = (string)($_SERVER['SCRIPT_NAME'] ?? '');
        if ($scriptName !== '' && strpos($requestPath, $scriptName) === 0) {
            $path = substr($requestPath, strlen($scriptName));
        } else {
            $path = $requestPath;
        }
    }
    $path = trim(rawurldecode($path), '/');
    if ($path === '') {
        return [];
    }
    return array_values(array_filter(explode('/', $path), function (string $part): bool {
        return $part !== '';
    }));
}

function data_dir(): string
{
    $configured = getenv('PAN_TRIAL_ROOM_DIR');
    $dir = $configured !== false && trim($configured) !== ''
        ? trim($configured)
        : __DIR__ . DIRECTORY_SEPARATOR . 'pan_trial_room_data';
    if (!is_dir($dir) && !mkdir($dir, 0775, true) && !is_dir($dir)) {
        throw new RuntimeException('Could not create room data directory');
    }
    $htaccess = $dir . DIRECTORY_SEPARATOR . '.htaccess';
    if (!is_file($htaccess)) {
        @file_put_contents(
            $htaccess,
            "# Deny direct access to JSON files\n"
            . "<Files \"*.json\">\n"
            . "    Require all denied\n"
            . "</Files>\n\n"
            . "# Deny directory listing\n"
            . "Options -Indexes\n"
        );
    }
    return $dir;
}

function with_room_lock(callable $callback): array
{
    $dir = data_dir();
    $lockPath = $dir . DIRECTORY_SEPARATOR . 'rooms.lock';
    $lock = fopen($lockPath, 'c');
    if ($lock === false) {
        throw new RuntimeException('Could not open room lock');
    }
    try {
        if (!flock($lock, LOCK_EX)) {
            throw new RuntimeException('Could not lock room storage');
        }
        return $callback($dir);
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

function generate_room_code(string $dataDir): string
{
    for ($attempt = 0; $attempt < 200; $attempt++) {
        $code = (string)random_int(1000, 9999);
        if (!is_file(room_path($dataDir, $code))) {
            return $code;
        }
    }
    throw new RuntimeException('Could not allocate a room code');
}

function room_path(string $dataDir, string $code): string
{
    $clean = preg_replace('/[^0-9]/', '', $code);
    if ($clean === '') {
        throw new RuntimeException('Room was not found');
    }
    return $dataDir . DIRECTORY_SEPARATOR . 'room_' . $clean . '.json';
}

function load_room(string $dataDir, string $code): array
{
    $path = room_path($dataDir, $code);
    if (!is_file($path)) {
        throw new RuntimeException('Room was not found');
    }
    $decoded = json_decode((string)file_get_contents($path), true);
    if (!is_array($decoded)) {
        throw new RuntimeException('Room data is unreadable');
    }
    return $decoded;
}

function save_room(string $dataDir, array $room): void
{
    $code = (string)($room['room_code'] ?? '');
    $path = room_path($dataDir, $code);
    $json = json_encode($room, JSON_UNESCAPED_SLASHES);
    if ($json === false || file_put_contents($path, $json, LOCK_EX) === false) {
        throw new RuntimeException('Could not save room');
    }
}

function touch_room(array &$room): void
{
    $room['last_touched'] = time();
}

function cleanup_inactive_rooms(string $dataDir): void
{
    foreach (glob($dataDir . DIRECTORY_SEPARATOR . 'room_*.json') ?: [] as $path) {
        $decoded = json_decode((string)file_get_contents($path), true);
        $lastTouched = is_array($decoded) ? intval($decoded['last_touched'] ?? filemtime($path)) : filemtime($path);
        if (time() - $lastTouched > PAN_TRIAL_ROOM_TIMEOUT_SECONDS) {
            @unlink($path);
        }
    }
}

function active_room_count(string $dataDir): int
{
    return count(glob($dataDir . DIRECTORY_SEPARATOR . 'room_*.json') ?: []);
}

function ok(array $payload): array
{
    return ['status' => 200, 'payload' => $payload];
}

function respond_json(int $status, array $payload): void
{
    http_response_code($status);
    header('Content-Type: application/json');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
}
