const TOKEN_KEY = "panTrialBrowserToken";

const appState = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    currentPayload: null,
    pollTimer: null,
    selectedPlacementCardIndex: null,
    messageTimer: null,
};

const elements = {
    connectionPill: document.getElementById("connection-pill"),
    messageBar: document.getElementById("message-bar"),
    screens: {
        start: document.getElementById("start-screen"),
        room: document.getElementById("room-screen"),
        waiting: document.getElementById("waiting-screen"),
        game: document.getElementById("game-screen"),
    },
    startGameButton: document.getElementById("start-game-button"),
    roomBackButton: document.getElementById("room-back-button"),
    leaveRoomButton: document.getElementById("leave-room-button"),
    leaveGameButton: document.getElementById("leave-game-button"),
    createRoomButton: document.getElementById("create-room-button"),
    joinRoomButton: document.getElementById("join-room-button"),
    playerNameInput: document.getElementById("player-name-input"),
    roomCodeInput: document.getElementById("room-code-input"),
    waitingRoomCode: document.getElementById("waiting-room-code"),
    waitingMessage: document.getElementById("waiting-message"),
    waitingPlayerList: document.getElementById("waiting-player-list"),
    roomHeading: document.getElementById("room-heading"),
    playerHeading: document.getElementById("player-heading"),
    statusText: document.getElementById("status-text"),
    phaseText: document.getElementById("phase-text"),
    turnText: document.getElementById("turn-text"),
    playerPanels: document.getElementById("player-panels"),
    suitRoleList: document.getElementById("suit-role-list"),
    boardGrid: document.getElementById("board-grid"),
    controlsContent: document.getElementById("controls-content"),
    logSections: document.getElementById("log-sections"),
    noticeBanner: document.getElementById("notice-banner"),
};

function escapeHtml(text) {
    return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
        },
        ...options,
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
        throw new Error(data.error || "Request failed.");
    }
    return data;
}

function showScreen(name) {
    Object.entries(elements.screens).forEach(([key, node]) => {
        node.classList.toggle("active", key === name);
    });
}

function setConnection(text, connected = false) {
    elements.connectionPill.textContent = text;
    elements.connectionPill.classList.toggle("connected", connected);
}

function setMessage(text, kind = "error", timeoutMs = 3600) {
    window.clearTimeout(appState.messageTimer);
    elements.messageBar.textContent = text;
    elements.messageBar.className = `message-bar ${kind}`;
    if (!text) {
        elements.messageBar.classList.add("hidden");
        return;
    }
    appState.messageTimer = window.setTimeout(() => {
        elements.messageBar.className = "message-bar hidden";
        elements.messageBar.textContent = "";
    }, timeoutMs);
}

function saveToken(token) {
    appState.token = token;
    localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
    appState.token = "";
    localStorage.removeItem(TOKEN_KEY);
    appState.currentPayload = null;
    appState.selectedPlacementCardIndex = null;
}

function startPolling() {
    stopPolling();
    if (!appState.token) {
        return;
    }
    appState.pollTimer = window.setInterval(() => {
        void pollState();
    }, 900);
}

function stopPolling() {
    if (appState.pollTimer) {
        window.clearInterval(appState.pollTimer);
        appState.pollTimer = null;
    }
}

async function createRoom() {
    try {
        const payload = await requestJson("/api/create-room", {
            method: "POST",
            body: JSON.stringify({
                player_name: elements.playerNameInput.value.trim() || "Player",
                room_code: elements.roomCodeInput.value.trim().toUpperCase(),
            }),
        });
        handleSessionPayload(payload);
        setMessage(`Room ${payload.room.room_code} created.`, "success");
    } catch (error) {
        setMessage(error.message);
    }
}

async function joinRoom() {
    try {
        const payload = await requestJson("/api/join-room", {
            method: "POST",
            body: JSON.stringify({
                player_name: elements.playerNameInput.value.trim() || "Player",
                room_code: elements.roomCodeInput.value.trim().toUpperCase(),
            }),
        });
        handleSessionPayload(payload);
        setMessage(`Joined room ${payload.room.room_code}.`, "success");
    } catch (error) {
        setMessage(error.message);
    }
}

function handleSessionPayload(payload) {
    saveToken(payload.token);
    appState.currentPayload = payload;
    startPolling();
    updateView(payload);
}

async function pollState() {
    if (!appState.token) {
        return;
    }
    try {
        const payload = await requestJson(`/api/state?token=${encodeURIComponent(appState.token)}`);
        appState.currentPayload = payload;
        updateView(payload);
    } catch (error) {
        stopPolling();
        clearToken();
        setConnection("Not Connected", false);
        showScreen("room");
        setMessage(error.message);
    }
}

async function leaveRoom(returnScreen = "start") {
    const token = appState.token;
    stopPolling();
    if (token) {
        try {
            await requestJson("/api/leave", {
                method: "POST",
                body: JSON.stringify({ token }),
            });
        } catch (_error) {
            // Ignore leave errors while closing or resetting locally.
        }
    }
    clearToken();
    setConnection("Not Connected", false);
    showScreen(returnScreen);
}

async function sendAction(action) {
    if (!appState.token) {
        return;
    }
    try {
        const payload = await requestJson("/api/action", {
            method: "POST",
            body: JSON.stringify({
                token: appState.token,
                action,
            }),
        });
        appState.currentPayload = payload;
        updateView(payload);
    } catch (error) {
        setMessage(error.message);
    }
}

function updateView(payload) {
    const room = payload.room;
    if (payload.notice) {
        elements.noticeBanner.textContent = payload.notice;
        elements.noticeBanner.classList.remove("hidden");
    } else {
        elements.noticeBanner.classList.add("hidden");
        elements.noticeBanner.textContent = "";
    }

    if (room.status === "active" && payload.game) {
        setConnection(`Live Room ${room.room_code}`, true);
        renderGame(payload);
        showScreen("game");
        return;
    }

    setConnection(room.room_code ? `Room ${room.room_code}` : "Not Connected", room.status !== "closed");
    renderWaiting(payload);
    showScreen("waiting");
    if (room.status === "closed") {
        setMessage(room.message || "The room has closed.");
    }
}

function renderWaiting(payload) {
    const room = payload.room;
    elements.waitingRoomCode.textContent = room.room_code ? `Room ${room.room_code}` : "Room Not Connected";
    elements.waitingMessage.textContent = room.message || "Waiting for room updates.";
    elements.waitingPlayerList.innerHTML = room.players
        .map((player) => `<li>Player ${player.player_id + 1}: ${escapeHtml(player.player_name)}</li>`)
        .join("");
}

function renderGame(payload) {
    const { room, player, game } = payload;
    elements.roomHeading.textContent = room.room_code;
    elements.playerHeading.textContent = `You are Player ${player.player_id + 1}: ${player.player_name}`;
    elements.statusText.textContent = game.status_text;
    elements.phaseText.textContent = `Phase: ${game.phase}`;
    elements.turnText.textContent = `Current turn: Player ${game.current_player + 1}`;
    renderPlayerPanels(game.players, player.player_id);
    renderSuitRoles(game.suit_roles);
    renderBoard(game.board, game.controls);
    renderControls(game.controls, game.phase);
    renderLogs(game.logs);
}

function renderPlayerPanels(players, localPlayerId) {
    elements.playerPanels.innerHTML = players
        .map((player) => {
            const handMarkup = player.player_id === localPlayerId
                ? player.hand.map((entry) => `<span class="small-chip">${escapeHtml(entry.card.label)}</span>`).join("")
                : `<span class="small-chip">${player.hand_count} hidden card(s)</span>`;
            const damageMarkup = player.damage_cards
                .map((entry) => `<span class="small-chip">${escapeHtml(entry.card.label)}</span>`)
                .join("");
            const position = player.position ? player.position.label : "Unknown";
            return `
                <div class="player-card">
                    <h4>Player ${player.player_id + 1}: ${escapeHtml(player.player_name)}</h4>
                    <div class="card-meta">Position: ${escapeHtml(position)}</div>
                    <div class="card-meta">Damage: ${player.damage_total}</div>
                    <div class="card-meta">Hand</div>
                    <div class="tag-list">${handMarkup || '<span class="small-chip">None</span>'}</div>
                    <div class="card-meta">Damage Pile</div>
                    <div class="tag-list">${damageMarkup || '<span class="small-chip">None</span>'}</div>
                </div>
            `;
        })
        .join("");
}

function renderSuitRoles(suitRoles) {
    elements.suitRoleList.innerHTML = suitRoles
        .map((entry) => `<span class="tag">${escapeHtml(entry.family_name)} -> ${escapeHtml(entry.role)}</span>`)
        .join("");
}

function renderBoard(boardRows, controls) {
    elements.boardGrid.innerHTML = "";
    boardRows.flat().forEach((cell) => {
        const button = document.createElement("button");
        button.className = "board-cell";
        if (cell.is_hole) {
            button.classList.add("hole");
        }
        if (cell.target_type === "ballista") {
            button.classList.add("target-ballista");
        }
        if (cell.target_type === "placement") {
            button.classList.add("target-placement");
        }
        const cardLabel = cell.card ? escapeHtml(cell.card.label) : "Hole";
        const role = cell.role ? `<div class="cell-role">${escapeHtml(cell.role)}</div>` : "";
        const occupants = cell.occupants.map((id) => `<span class="occupant-badge">P${id + 1}</span>`).join("");
        button.innerHTML = `
            <div class="cell-top">
                <span>R${cell.row + 1} C${cell.col + 1}</span>
                ${cell.target_type ? `<span>${escapeHtml(cell.target_type)}</span>` : ""}
            </div>
            <div class="cell-card">${cardLabel}</div>
            ${role}
            <div class="cell-occupants">${occupants}</div>
        `;
        const canClickBallista = cell.target_type === "ballista" && controls.can_act;
        const canClickPlacement = cell.target_type === "placement" && controls.placement && controls.can_act;
        if (canClickBallista) {
            button.addEventListener("click", () => {
                void sendAction({
                    type: "resolve_ballista_shot",
                    row: cell.row,
                    col: cell.col,
                });
            });
        } else if (canClickPlacement) {
            button.addEventListener("click", () => {
                if (appState.selectedPlacementCardIndex == null) {
                    setMessage("Select a played card first.");
                    return;
                }
                void sendAction({
                    type: "place_card",
                    card_index: appState.selectedPlacementCardIndex,
                    row: cell.row,
                    col: cell.col,
                });
            });
        } else {
            button.classList.add("disabled");
            button.disabled = true;
        }
        elements.boardGrid.appendChild(button);
    });
}

function appendSection(title, innerHtml) {
    const section = document.createElement("section");
    section.className = "control-section";
    section.innerHTML = `<h3>${escapeHtml(title)}</h3>${innerHtml}`;
    elements.controlsContent.appendChild(section);
}

function renderControls(controls, phase) {
    elements.controlsContent.innerHTML = "";

    if (controls.movement.length || controls.can_pick_up_current) {
        const buttons = controls.movement
            .map((direction) => (
                `<button class="control-button accent" data-action="move" data-direction="${escapeHtml(direction)}">Move ${escapeHtml(direction)}</button>`
            ))
            .join("");
        const pickup = controls.can_pick_up_current
            ? `<button class="control-button accent" data-action="pickup">Use Current Tile</button>`
            : "";
        appendSection("Traversing", `<div class="control-grid">${buttons}${pickup}</div>`);
    }

    if (controls.hand_cards.length) {
        const cards = controls.hand_cards.map((entry) => {
            let actionType = "";
            let actionLabel = "View Only";
            if (entry.can_use_weapon) {
                actionType = "choose_combat_card";
                actionLabel = "Use Weapon";
            } else if (entry.can_play) {
                actionType = "play_card";
                actionLabel = phase === "appeasing" ? "Play Card" : "Select";
            }
            return `
                <div class="hand-card">
                    <h4>${escapeHtml(entry.card.label)}</h4>
                    <div class="card-meta">Role: ${escapeHtml(entry.role || "unknown")}</div>
                    <div class="card-meta">Value: ${entry.card.combat_value}</div>
                    <button
                        class="control-button ${actionType ? "accent" : ""}"
                        ${actionType ? `data-action="${actionType}" data-card-index="${entry.index}"` : "disabled"}
                    >${escapeHtml(actionLabel)}</button>
                </div>
            `;
        }).join("");
        appendSection("Your Hand", `<div class="card-list">${cards}</div>`);
    }

    if (controls.request_types.length) {
        const buttons = controls.request_types
            .map((requestType) => (
                `<button class="control-button accent" data-action="choose_request" data-request-type="${escapeHtml(requestType)}">${escapeHtml(requestType.replaceAll("_", " "))}</button>`
            ))
            .join("");
        appendSection("Choose Pan's Request", `<div class="control-grid">${buttons}</div>`);
    }

    if (controls.restructure_suits.length) {
        const buttons = controls.restructure_suits
            .map((entry) => `
                <button
                    class="control-button ${entry.selected ? "selected" : "accent"}"
                    data-action="select_restructure_suit"
                    data-suit="${escapeHtml(entry.suit)}"
                    ${entry.selected ? "disabled" : ""}
                >${escapeHtml(entry.family_name)} (${escapeHtml(entry.role)})</button>
            `)
            .join("");
        appendSection("Restructure", `<div class="control-grid">${buttons}</div>`);
    }

    if (controls.steal_life) {
        const ownCards = controls.steal_life.own_cards
            .map((entry) => `
                <button
                    class="control-button ${controls.steal_life.selected_own_index === entry.index ? "selected" : "accent"}"
                    data-action="select_damage_card"
                    data-pile-owner="0"
                    data-card-index="${entry.index}"
                >Your: ${escapeHtml(entry.card.label)}</button>
            `)
            .join("");
        const enemyCards = controls.steal_life.enemy_cards
            .map((entry) => `
                <button
                    class="control-button accent"
                    data-action="select_damage_card"
                    data-pile-owner="1"
                    data-card-index="${entry.index}"
                >Enemy: ${escapeHtml(entry.card.label)}</button>
            `)
            .join("");
        appendSection(
            "Steal Life",
            `<p class="panel-copy">Choose one of your damage cards first, then one from the enemy pile.</p>
             <div class="control-grid">${ownCards}${enemyCards}</div>`
        );
    }

    if (controls.plane_shift) {
        const directionButtons = controls.plane_shift.directions
            .map((direction) => `
                <button class="control-button accent" data-action="select_plane_shift_direction" data-direction="${escapeHtml(direction)}">
                    Shift ${escapeHtml(direction)}
                </button>
            `)
            .join("");
        const axisLabel = controls.plane_shift.axis ? `Choose ${escapeHtml(controls.plane_shift.axis)}:` : "";
        const indexButtons = controls.plane_shift.indices
            .map((index) => `
                <button class="control-button accent" data-action="resolve_plane_shift" data-index="${index}">
                    ${escapeHtml((index + 1).toString())}
                </button>
            `)
            .join("");
        appendSection(
            "Plane Shift",
            `<div class="control-grid">${directionButtons}</div>
             <p class="panel-copy">${axisLabel}</p>
             <div class="control-grid">${indexButtons}</div>`
        );
    }

    if (controls.ballista_targets.length) {
        appendSection(
            "Ballista",
            `<p class="panel-copy">Click one of the highlighted board cells to choose a Ballista destination.</p>`
        );
    }

    if (controls.placement) {
        if (
            appState.selectedPlacementCardIndex == null
            || !controls.placement.cards.some((entry) => entry.index === appState.selectedPlacementCardIndex)
        ) {
            appState.selectedPlacementCardIndex = controls.placement.cards[0]?.index ?? null;
        }
        const cardButtons = controls.placement.cards
            .map((entry) => `
                <button
                    class="control-button ${appState.selectedPlacementCardIndex === entry.index ? "selected" : "accent"}"
                    data-action="select-placement-card"
                    data-card-index="${entry.index}"
                >${escapeHtml(entry.card.label)}</button>
            `)
            .join("");
        const holeButtons = controls.placement.holes
            .map((entry) => `
                <button
                    class="control-button"
                    data-action="place_card"
                    data-card-index="${appState.selectedPlacementCardIndex ?? ""}"
                    data-row="${entry.row}"
                    data-col="${entry.col}"
                >${escapeHtml(entry.label)}</button>
            `)
            .join("");
        appendSection(
            "Place Played Cards",
            `<p class="panel-copy">Select a played card, then click a highlighted hole on the board or one of the hole buttons below.</p>
             <div class="control-grid">${cardButtons}</div>
             <div class="control-grid">${holeButtons}</div>`
        );
    }

    if (!elements.controlsContent.children.length) {
        appendSection("Controls", `<p class="panel-copy">No clickable controls are available right now. ${controls.can_act ? "Watch the board for highlighted targets or wait for the next prompt." : "The game is waiting on the other player."}</p>`);
    }

    bindControlActions();
}

function bindControlActions() {
    elements.controlsContent.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", () => {
            const actionType = button.dataset.action;
            if (actionType === "move") {
                void sendAction({ type: "move", direction: button.dataset.direction });
                return;
            }
            if (actionType === "pickup") {
                void sendAction({ type: "pickup_current" });
                return;
            }
            if (actionType === "play_card") {
                void sendAction({ type: "play_card", card_index: Number(button.dataset.cardIndex) });
                return;
            }
            if (actionType === "choose_combat_card") {
                void sendAction({ type: "choose_combat_card", card_index: Number(button.dataset.cardIndex) });
                return;
            }
            if (actionType === "choose_request") {
                void sendAction({ type: "choose_request", request_type: button.dataset.requestType });
                return;
            }
            if (actionType === "select_damage_card") {
                const pileOwner = Number(button.dataset.pileOwner);
                const payloadPile = pileOwner === 0 ? appState.currentPayload.player.player_id : 1 - appState.currentPayload.player.player_id;
                void sendAction({
                    type: "select_damage_card",
                    pile_owner: payloadPile,
                    card_index: Number(button.dataset.cardIndex),
                });
                return;
            }
            if (actionType === "select_restructure_suit") {
                void sendAction({ type: "select_restructure_suit", suit: button.dataset.suit });
                return;
            }
            if (actionType === "select_plane_shift_direction") {
                void sendAction({ type: "select_plane_shift_direction", direction: button.dataset.direction });
                return;
            }
            if (actionType === "resolve_plane_shift") {
                void sendAction({ type: "resolve_plane_shift", index: Number(button.dataset.index) });
                return;
            }
            if (actionType === "select-placement-card") {
                appState.selectedPlacementCardIndex = Number(button.dataset.cardIndex);
                renderControls(appState.currentPayload.game.controls, appState.currentPayload.game.phase);
                return;
            }
            if (actionType === "place_card") {
                const cardIndex = appState.selectedPlacementCardIndex;
                if (cardIndex == null) {
                    setMessage("Select a played card first.");
                    return;
                }
                void sendAction({
                    type: "place_card",
                    card_index: cardIndex,
                    row: Number(button.dataset.row),
                    col: Number(button.dataset.col),
                });
            }
        });
    });
}

function renderLogs(logs) {
    const sections = [
        ["Events", logs.events],
        ["Appeasing", logs.appeasing],
        ["Requests", logs.requests],
    ];
    elements.logSections.innerHTML = sections.map(([title, lines]) => `
        <div class="log-block">
            <h4>${escapeHtml(title)}</h4>
            <div class="log-list">
                ${(lines && lines.length ? lines : ["None yet."])
                    .map((line) => `<div>${escapeHtml(line)}</div>`)
                    .join("")}
            </div>
        </div>
    `).join("");
}

function restoreOrShowStart() {
    if (appState.token) {
        startPolling();
        void pollState();
        return;
    }
    showScreen("start");
    setConnection("Not Connected", false);
}

elements.startGameButton.addEventListener("click", () => showScreen("room"));
elements.roomBackButton.addEventListener("click", () => showScreen("start"));
elements.createRoomButton.addEventListener("click", () => void createRoom());
elements.joinRoomButton.addEventListener("click", () => void joinRoom());
elements.leaveRoomButton.addEventListener("click", () => void leaveRoom("room"));
elements.leaveGameButton.addEventListener("click", () => void leaveRoom("room"));
elements.roomCodeInput.addEventListener("input", () => {
    elements.roomCodeInput.value = elements.roomCodeInput.value.toUpperCase().replaceAll(/[^A-Z0-9]/g, "");
});

window.addEventListener("beforeunload", () => {
    if (!appState.token) {
        return;
    }
    const body = JSON.stringify({ token: appState.token });
    navigator.sendBeacon("/api/leave", new Blob([body], { type: "application/json" }));
});

restoreOrShowStart();
