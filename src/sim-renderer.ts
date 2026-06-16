import './style.css';
import { SCRenderer } from './engine/SCRenderer';

type Team = 'blue' | 'red';

type RenderEntity = {
    id: number;
    card: string;
    name: string;
    team: Team;
    type: 'troop' | 'building' | 'tower';
    x: number;
    y: number;
    hp: number;
    max_hp: number;
    radius: number;
    is_moving: boolean;
    is_attacking: boolean;
    attack_cooldown: number;
    action_frame_timer: number;
    hit_speed: number;
    load_time: number;
    facing_direction: { x: number; y: number };
    activation_state: 'asleep' | 'activating' | 'awake';
    activation_timer: number;
    effect: string;
    path_points: Array<{ x: number; y: number }>;
};

type RenderProjectile = {
    id: number;
    source: string;
    team: Team;
    x: number;
    y: number;
    start_x: number;
    start_y: number;
    target_x: number;
    target_y: number;
    asset: string | null;
    trajectory: 'line' | 'parabola' | null;
};

type RenderEffect = {
    id: number;
    name: string;
    x: number;
    y: number;
    start_time: number;
    file_name: string | null;
};

type AoeCircle = {
    id: number;
    x: number;
    y: number;
    radius: number;
    duration: number;
};

type RenderCard = {
    id: string;
    name: string;
    elixir_cost: number;
};

type RenderState = {
    time?: number;
    elixir?: Partial<Record<Team, number>>;
    hands?: Partial<Record<Team, RenderCard[]>>;
    decks?: Partial<Record<Team, RenderCard[]>>;
    arena?: {
        width: number;
        height: number;
        river_y_start: number;
        river_y_end: number;
        left_bridge_x: number;
        right_bridge_x: number;
        bridge_width: number;
    };
    entities?: RenderEntity[];
    projectiles?: RenderProjectile[];
    effects?: RenderEffect[];
    aoe_circles?: AoeCircle[];
};

const params = new URLSearchParams(window.location.search);
const stateUrl = params.get('state');
const container = document.getElementById('game-container') as HTMLDivElement;
const statusEl = document.getElementById('status') as HTMLElement;

const ARENA = {
    width: 18,
    height: 32,
    river_y_start: 15,
    river_y_end: 17,
    left_bridge_x: 2,
    right_bridge_x: 14,
    bridge_width: 2,
};

const pxPerTileX = container.clientWidth / ARENA.width;
const pxPerTileY = container.clientHeight / ARENA.height;
const entityDivs = new Map<number, HTMLDivElement>();
const projectileDivs = new Set<number>();
const effectIds = new Set<number>();
const aoeDivs = new Map<number, HTMLDivElement>();
const pathEls = new Map<number, SVGPolylineElement>();
const pathSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
const preloadedCardImages = new Set<string>();
const DEFAULT_CARD_IDS = ['knight', 'archers', 'giant', 'pekka', 'musketeer', 'hog_rider', 'skeletons', 'wizard'];

type HandRefs = {
    root: HTMLDivElement;
    slots: HTMLDivElement[];
};

type StatusRefs = {
    bridge: HTMLSpanElement;
    time: HTMLSpanElement;
    entityCount: HTMLSpanElement;
    projectileCount: HTMLSpanElement;
    elixir: Record<Team, { value: HTMLElement; fills: HTMLSpanElement[] }>;
    hands: Record<Team, HandRefs>;
};

const statusRefs = createStatusShell();

function addArenaDecor() {
    const river = document.createElement('div');
    river.style.position = 'absolute';
    river.style.backgroundColor = '#4a90e2';
    river.style.left = '0';
    river.style.top = `${ARENA.river_y_start * pxPerTileY}px`;
    river.style.width = '100%';
    river.style.height = `${(ARENA.river_y_end - ARENA.river_y_start) * pxPerTileY}px`;
    river.style.zIndex = '1';
    container.appendChild(river);

    [ARENA.left_bridge_x, ARENA.right_bridge_x].forEach((x) => {
        const bridge = document.createElement('div');
        bridge.style.position = 'absolute';
        bridge.style.backgroundColor = '#8b5a2b';
        bridge.style.left = `${x * pxPerTileX}px`;
        bridge.style.top = `${ARENA.river_y_start * pxPerTileY}px`;
        bridge.style.width = `${ARENA.bridge_width * pxPerTileX}px`;
        bridge.style.height = `${(ARENA.river_y_end - ARENA.river_y_start) * pxPerTileY}px`;
        bridge.style.zIndex = '2';
        container.appendChild(bridge);
    });

    pathSvg.style.position = 'absolute';
    pathSvg.style.left = '0';
    pathSvg.style.top = '0';
    pathSvg.style.width = '100%';
    pathSvg.style.height = '100%';
    pathSvg.style.pointerEvents = 'none';
    pathSvg.style.zIndex = '5';
    container.appendChild(pathSvg);
}

async function loadMappings() {
    const chars = [
        'chr_knight',
        'chr_archer',
        'chr_giant',
        'chr_pekka',
        'chr_minion',
        'chr_skeleton',
        'chr_barbarian',
        'chr_musketeer',
        'chr_hog_rider',
        'chr_wizard',
        'chr_princess',
        'building_tower',
        'effects',
    ];
    await Promise.all(chars.map((charId) => SCRenderer.loadCharacter(charId)));
}

function cardImageSrc(cardId: string) {
    return `${import.meta.env.BASE_URL}assets/cards/${cardId.replaceAll('_', '-')}.png`;
}

function preloadCardImages(cards: RenderCard[]) {
    preloadCardIds(cards.map((card) => card.id));
}

function preloadCardIds(cardIds: string[]) {
    for (const cardId of cardIds) {
        const src = cardImageSrc(cardId);
        if (preloadedCardImages.has(src)) continue;
        const image = new Image();
        image.src = src;
        preloadedCardImages.add(src);
    }
}

function createMetric(label: string) {
    const row = document.createElement('div');
    row.className = 'metric';
    const labelEl = document.createElement('span');
    const valueEl = document.createElement('span');
    labelEl.textContent = label;
    row.append(labelEl, valueEl);
    return { row, valueEl };
}

function createElixirRow(team: Team) {
    const row = document.createElement('div');
    row.className = `elixir-row ${team}`;

    const label = document.createElement('span');
    label.textContent = team === 'blue' ? 'Blue' : 'Red';

    const track = document.createElement('div');
    track.className = 'elixir-track';
    const fills = Array.from({ length: 10 }, () => {
        const segment = document.createElement('span');
        segment.className = 'elixir-segment';
        const fill = document.createElement('span');
        segment.appendChild(fill);
        track.appendChild(segment);
        return fill;
    });

    const value = document.createElement('strong');
    row.append(label, track, value);
    return { row, value, fills };
}

function createHandPanel(team: Team): HandRefs {
    const root = document.createElement('div');
    root.className = `hand-panel ${team}`;

    const title = document.createElement('div');
    title.className = 'hand-title';
    title.textContent = team === 'blue' ? 'Blue Hand' : 'Red Hand';

    const slotGrid = document.createElement('div');
    slotGrid.className = 'card-slots';
    const slots = Array.from({ length: 4 }, () => {
        const slot = document.createElement('div');
        slot.className = 'card-slot empty';
        slotGrid.appendChild(slot);
        return slot;
    });

    root.append(title, slotGrid);
    return { root, slots };
}

function createStatusShell(): StatusRefs {
    statusEl.replaceChildren();

    const bridgeMetric = createMetric('Bridge');
    const timeMetric = createMetric('Time');
    const entityMetric = createMetric('Entities');
    const projectileMetric = createMetric('Projectiles');
    const redHand = createHandPanel('red');
    const blueHand = createHandPanel('blue');

    const elixirPanel = document.createElement('div');
    elixirPanel.className = 'elixir-panel';
    const redElixir = createElixirRow('red');
    const blueElixir = createElixirRow('blue');
    elixirPanel.append(redElixir.row, blueElixir.row);

    statusEl.append(
        bridgeMetric.row,
        timeMetric.row,
        redHand.root,
        elixirPanel,
        blueHand.root,
        entityMetric.row,
        projectileMetric.row,
    );

    return {
        bridge: bridgeMetric.valueEl,
        time: timeMetric.valueEl,
        entityCount: entityMetric.valueEl,
        projectileCount: projectileMetric.valueEl,
        elixir: {
            red: { value: redElixir.value, fills: redElixir.fills },
            blue: { value: blueElixir.value, fills: blueElixir.fills },
        },
        hands: {
            red: redHand,
            blue: blueHand,
        },
    };
}

function charPrefix(entity: RenderEntity) {
    const charNameMap: Record<string, string> = {
        Knight: 'knight',
        Archers: 'archer',
        Giant: 'giant',
        'P.E.K.K.A': 'pekka',
        Minions: 'minion',
        Skeletons: 'skeleton',
        Barbarians: 'barbarian',
        'Elite Barbarians': 'barbarian',
        Musketeer: 'musketeer',
        'Hog Rider': 'hog_rider',
        'Battle Healer': 'battle_healer',
        Princess: 'princess',
        Wizard: 'wizard',
    };
    if (entity.name === 'Princess Tower' || entity.name === 'King Tower') return 'building_tower';
    const folder = charNameMap[entity.name];
    return folder ? `chr_${folder}` : null;
}

function directionSuffix(entity: RenderEntity) {
    const dir = entity.facing_direction || { x: 0, y: 1 };
    let angle = Math.atan2(dir.y, dir.x) * 180 / Math.PI;
    if (angle < 0) angle += 360;
    if (angle >= 67.5 && angle < 112.5) return '8';
    if (angle >= 112.5 && angle < 157.5) return '9';
    if (angle >= 157.5 && angle < 202.5) return '4';
    if (angle >= 202.5 && angle < 247.5) return '1';
    if (angle >= 247.5 && angle < 292.5) return '2';
    if (angle >= 292.5 && angle < 337.5) return '3';
    if (angle >= 337.5 || angle < 22.5) return '6';
    return '7';
}

function entityAction(entity: RenderEntity) {
    let action = 'idle';
    let animProgress = -1;
    const attackAnimDuration = 0.4;

    if (entity.is_attacking) {
        const loadTime = entity.load_time || (entity.hit_speed * 0.5);
        const elapsed = loadTime - entity.action_frame_timer;
        if (loadTime > attackAnimDuration) {
            if (elapsed < loadTime - attackAnimDuration) {
                action = 'idle';
            } else {
                action = 'attack';
                animProgress = 0.5 * ((elapsed - (loadTime - attackAnimDuration)) / attackAnimDuration);
            }
        } else {
            action = 'attack';
            animProgress = 0.5 * (elapsed / loadTime);
        }
    } else if (entity.is_moving) {
        action = 'run';
    } else if (entity.attack_cooldown > 0) {
        const loadTime = entity.load_time || (entity.hit_speed * 0.5);
        const cooldownTotal = entity.hit_speed - loadTime;
        const elapsedAfterHit = cooldownTotal - entity.attack_cooldown;
        const followThroughDuration = Math.min(Math.min(loadTime, attackAnimDuration), cooldownTotal);
        if (followThroughDuration > 0 && elapsedAfterHit < followThroughDuration) {
            action = 'attack';
            animProgress = 0.5 + 0.5 * (elapsedAfterHit / followThroughDuration);
        }
    }

    if (animProgress !== -1) animProgress = Math.max(0, Math.min(1, animProgress));
    return { action, animProgress };
}

function updateEntity(entity: RenderEntity, frameIndex: number) {
    let div = entityDivs.get(entity.id);
    if (!div) {
        div = document.createElement('div');
        div.className = entity.type === 'tower' ? 'tower' : 'entity';
        const hpText = document.createElement('div');
        hpText.className = 'hp-text';
        div.appendChild(hpText);
        container.appendChild(div);
        entityDivs.set(entity.id, div);
    }

    div.style.left = `${entity.x * pxPerTileX}px`;
    div.style.top = `${entity.y * pxPerTileY}px`;
    div.style.width = `${entity.radius * 2 * pxPerTileX}px`;
    div.style.height = `${entity.radius * 2 * pxPerTileY}px`;
    div.style.backgroundColor = 'transparent';
    div.style.border = 'none';

    const hpText = div.querySelector('.hp-text') as HTMLDivElement;
    hpText.innerText = Math.ceil(entity.hp).toString();
    hpText.style.color = entity.team === 'blue' ? '#4ade80' : '#f87171';

    const prefix = charPrefix(entity);
    if (!prefix) {
        div.style.backgroundColor = entity.team === 'blue' ? '#3498db' : '#e74c3c';
        div.style.borderRadius = '50%';
        return;
    }

    const isTower = entity.name === 'Princess Tower' || entity.name === 'King Tower';
    const { action, animProgress: baseAnimProgress } = entityAction(entity);
    const actionToPass = isTower
        ? entity.name === 'Princess Tower'
            ? entity.team === 'red'
                ? 'StarTower_base_red'
                : 'StarTower_base_blue'
            : entity.team === 'red'
                ? 'KingTower_red'
                : 'KingTower_blue'
        : action;

    let finalFrameIndex = frameIndex;
    let animProgress = baseAnimProgress;
    let aimAngle = -1;
    let overrideFlipX: boolean | null = null;

    if (entity.name === 'King Tower') {
        if (entity.activation_state === 'asleep') {
            finalFrameIndex = 0;
            animProgress = -1;
        } else if (entity.activation_state === 'activating') {
            animProgress = Math.max(0, 1 - (entity.activation_timer / (97 / 30)));
            finalFrameIndex = 97;
        } else {
            finalFrameIndex = 97;
            animProgress = -1;
            let angleDeg = Math.atan2(entity.facing_direction.y, entity.facing_direction.x) * 180 / Math.PI;
            if (angleDeg < 0) angleDeg += 360;
            const scAngle = (angleDeg + 90) % 360;
            if (scAngle <= 180) {
                overrideFlipX = false;
                aimAngle = Math.min(35, Math.round(scAngle / 5));
            } else {
                overrideFlipX = true;
                aimAngle = Math.min(35, Math.round((360 - scAngle) / 5));
            }
        }
    }

    SCRenderer.updateEntity(
        entity.id,
        prefix,
        actionToPass,
        directionSuffix(entity),
        entity.team === 'red',
        finalFrameIndex,
        entity.x * pxPerTileX,
        entity.y * pxPerTileY,
        0.55,
        action,
        aimAngle,
        overrideFlipX,
        animProgress,
        frameIndex,
    );

    div.style.opacity = entity.effect === 'cloaking_cape' ? '0.4' : '1';
    div.style.boxShadow = entity.effect !== 'none' && entity.effect !== 'cloaking_cape' ? '0 0 10px 5px yellow' : 'none';
}

function updateProjectile(projectile: RenderProjectile) {
    let angle = Math.atan2(projectile.target_y - projectile.y, projectile.target_x - projectile.x) * 180 / Math.PI;
    if (angle < 0) angle += 360;
    let exportName = projectile.asset || 'projectile_arrow_basic';
    if (exportName === 'projectile_arrow_basic' && projectile.team === 'red') {
        exportName = 'projectile_arrow_basic_enemy';
    }

    const totalDist = Math.hypot(projectile.target_x - projectile.start_x, projectile.target_y - projectile.start_y);
    const currentDist = Math.hypot(projectile.x - projectile.start_x, projectile.y - projectile.start_y);
    const progress = totalDist > 0 ? Math.max(0, Math.min(1, currentDist / totalDist)) : 1;
    const startHeight = projectile.source === 'king_tower' ? -25 : projectile.source === 'princess_tower' || projectile.source === 'princess' ? -40 : -20;
    const endHeight = -15;
    const arcOffset = projectile.trajectory === 'parabola' ? Math.sin(progress * Math.PI) * -30 : 0;
    const currentZOffset = startHeight + (endHeight - startHeight) * progress + arcOffset;

    SCRenderer.updateProjectile(projectile.id, exportName, angle, projectile.x * pxPerTileX, projectile.y * pxPerTileY + currentZOffset, projectile.trajectory === 'parabola' ? 0.7 : 0.6);
    projectileDivs.add(projectile.id);
}

function updatePaths(entity: RenderEntity) {
    if (entity.path_points.length > 0 && entity.is_moving) {
        let pathEl = pathEls.get(entity.id);
        if (!pathEl) {
            pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
            pathEl.setAttribute('fill', 'none');
            pathEl.setAttribute('stroke', entity.team === 'blue' ? 'rgba(52, 152, 219, 0.5)' : 'rgba(231, 76, 60, 0.5)');
            pathEl.setAttribute('stroke-width', '4');
            pathEl.setAttribute('stroke-dasharray', '5, 5');
            pathSvg.appendChild(pathEl);
            pathEls.set(entity.id, pathEl);
        }
        pathEl.setAttribute('points', [{ x: entity.x, y: entity.y }, ...entity.path_points].map((point) => `${point.x * pxPerTileX},${point.y * pxPerTileY}`).join(' '));
    } else {
        pathEls.get(entity.id)?.remove();
        pathEls.delete(entity.id);
    }
}

function updateEffects(state: RenderState, frameIndex: number) {
    const currentEffectIds = new Set((state.effects || []).map((effect) => effect.id));
    for (const effect of state.effects || []) {
        effectIds.add(effect.id);
        SCRenderer.updateEffect(effect.id, effect.name, effect.x * pxPerTileX, effect.y * pxPerTileY, 0.55, Math.floor(((state.time || 0) - effect.start_time) * 30), effect.file_name || 'effects');
    }
    for (const id of [...effectIds]) {
        if (!currentEffectIds.has(id)) {
            SCRenderer.removeEffect(id);
            effectIds.delete(id);
        }
    }

    const currentAoeIds = new Set((state.aoe_circles || []).map((circle) => circle.id));
    for (const [id, div] of aoeDivs.entries()) {
        if (!currentAoeIds.has(id)) {
            div.remove();
            aoeDivs.delete(id);
        }
    }
    for (const circle of state.aoe_circles || []) {
        let div = aoeDivs.get(circle.id);
        if (!div) {
            div = document.createElement('div');
            div.style.position = 'absolute';
            div.style.border = '2px solid rgba(255, 100, 100, 0.6)';
            div.style.backgroundColor = 'rgba(255, 50, 50, 0.2)';
            div.style.borderRadius = '50%';
            div.style.pointerEvents = 'none';
            div.style.zIndex = '5';
            div.style.transform = 'translate(-50%, -50%)';
            div.style.transition = `opacity ${circle.duration}s ease-out`;
            container.appendChild(div);
            aoeDivs.set(circle.id, div);
            requestAnimationFrame(() => {
                if (div) div.style.opacity = '0';
            });
        }
        const radiusPx = circle.radius * pxPerTileX;
        div.style.width = `${radiusPx * 2}px`;
        div.style.height = `${radiusPx * 2}px`;
        div.style.left = `${circle.x * pxPerTileX}px`;
        div.style.top = `${circle.y * pxPerTileY}px`;
    }
}

function updateElixirRow(team: Team, value: number) {
    const clamped = Math.min(10, Math.max(0, value));
    statusRefs.elixir[team].value.textContent = clamped.toFixed(1);
    statusRefs.elixir[team].fills.forEach((fillEl, index) => {
        const fill = Math.min(1, Math.max(0, clamped - index));
        fillEl.style.width = `${fill * 100}%`;
    });
}

function updateHand(team: Team, cards: RenderCard[]) {
    statusRefs.hands[team].slots.forEach((slot, index) => {
        const card = cards[index];
        if (!card) {
            if (slot.dataset.cardId !== '') {
                slot.dataset.cardId = '';
                slot.className = 'card-slot empty';
                slot.replaceChildren();
            }
            return;
        }

        if (slot.dataset.cardId === card.id) return;

        const image = document.createElement('img');
        image.src = cardImageSrc(card.id);
        image.alt = card.name;

        const cost = document.createElement('strong');
        cost.textContent = String(card.elixir_cost);

        slot.dataset.cardId = card.id;
        slot.className = 'card-slot';
        slot.replaceChildren(image, cost);
    });
}

function renderState(state: RenderState) {
    const entities = state.entities || [];
    const projectiles = state.projectiles || [];
    const blueElixir = state.elixir?.blue ?? 0;
    const redElixir = state.elixir?.red ?? 0;
    const blueHand = state.hands?.blue || [];
    const redHand = state.hands?.red || [];
    const currentEntityIds = new Set(entities.map((entity) => entity.id));
    const currentProjectileIds = new Set(projectiles.map((projectile) => projectile.id));
    const frameIndex = Math.floor(performance.now() / 1000 * 30);

    for (const [id, div] of entityDivs.entries()) {
        if (!currentEntityIds.has(id)) {
            div.remove();
            entityDivs.delete(id);
            SCRenderer.removeEntity(id);
            pathEls.get(id)?.remove();
            pathEls.delete(id);
        }
    }

    for (const id of [...projectileDivs]) {
        if (!currentProjectileIds.has(id)) {
            SCRenderer.removeProjectile(id);
            projectileDivs.delete(id);
        }
    }

    entities.forEach((entity) => {
        updateEntity(entity, frameIndex);
        updatePaths(entity);
    });
    projectiles.forEach(updateProjectile);
    updateEffects(state, frameIndex);

    preloadCardImages([...(state.decks?.red || redHand), ...(state.decks?.blue || blueHand)]);
    statusRefs.bridge.textContent = stateUrl ? 'connected' : 'missing';
    statusRefs.time.textContent = `${(state.time || 0).toFixed(2)}s`;
    statusRefs.entityCount.textContent = String(entities.length);
    statusRefs.projectileCount.textContent = String(projectiles.length);
    updateElixirRow('red', redElixir);
    updateElixirRow('blue', blueElixir);
    updateHand('red', redHand);
    updateHand('blue', blueHand);
}

async function poll() {
    if (!stateUrl) {
        statusRefs.bridge.textContent = 'missing';
        return;
    }

    try {
        const res = await fetch(stateUrl, { cache: 'no-store' });
        if (res.ok) renderState(await res.json());
    } catch {
        statusRefs.bridge.textContent = 'waiting';
    } finally {
        window.setTimeout(poll, 50);
    }
}

async function boot() {
    preloadCardIds(DEFAULT_CARD_IDS);
    addArenaDecor();
    await SCRenderer.init(container);
    await loadMappings();
    await poll();
}

boot();
