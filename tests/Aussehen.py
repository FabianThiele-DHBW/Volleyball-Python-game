# volleyball_ursina.py
from ursina import *
from math import copysign

app = Ursina()

# ---------------------------
# Szene / Kamera / Licht
# ---------------------------
window.title = 'Mini Volleyball 3D (Ursina)'
window.color = color.rgb(120, 180, 255)

Sky()
DirectionalLight(shadows=True, rotation=(45, -45, 0))

# Kamera leicht schräg über dem Feld
camera.position = (0, 20, -28)
camera.look_at((0, 3, 0))

# ---------------------------
# Spielfeld / Netz
# ---------------------------
FIELD_HALF_X = 12        # Feldhälfte in X-Richtung (links/rechts)
FIELD_HALF_Z = 7         # Feldhälfte in Z-Richtung (vor/zurück)
NET_HEIGHT = 3.0
NET_THICKNESS = 0.25

ground = Entity(model='plane', scale=(FIELD_HALF_X*2, 1, FIELD_HALF_Z*2),
                color=color.lime.tint(-.25), texture='white_cube', texture_scale=(12, 8),
                collider='box')

# Netz als dünner Würfel entlang Z
net = Entity(model='cube', color=color.white, position=(0, NET_HEIGHT/2, 0),
             scale=(NET_THICKNESS, NET_HEIGHT, FIELD_HALF_Z*2), collider='box')

# Linien (optional, nur optisch)
line_left = Entity(model='cube', color=color.white33, position=(-FIELD_HALF_X, 0.02, 0),
                   scale=(0.1, 0.04, FIELD_HALF_Z*2))
line_right = duplicate(line_left, x=FIELD_HALF_X)
line_back1 = Entity(model='cube', color=color.white33, position=(0, 0.02, -FIELD_HALF_Z),
                    scale=(FIELD_HALF_X*2, 0.04, 0.1))
line_back2 = duplicate(line_back1, z=FIELD_HALF_Z)

# ---------------------------
# Spieler
# ---------------------------
PLAYER_W = 1.2
PLAYER_H = 2.2
PLAYER_D = 1.2
MOVE_SPEED = 8.5
JUMP_FORCE = 10.5
PLAYER_GRAV = -28


def create_human_player(player_color, position):
    """Erstelle Spieler aus Kopf, Körper und Beinen."""
    # Größere Hitbox für leicheres Treffen (2x breiter/tiefer)
    player = Entity(position=position, collider='box', scale=(PLAYER_W*2.0, PLAYER_H*1.2, PLAYER_D*2.0))
    # Körper (Torso)
    Entity(parent=player, model='cube', color=player_color, scale=(0.7, 1.0, 0.5), y=0.3)
    # Kopf
    Entity(parent=player, model='sphere', color=player_color.tint(-0.1), scale=0.5, y=1.1)
    # Linkes Bein
    Entity(parent=player, model='cube', color=player_color, scale=(0.2, 0.8, 0.2), x=-0.2, y=-0.5)
    # Rechtes Bein
    Entity(parent=player, model='cube', color=player_color, scale=(0.2, 0.8, 0.2), x=0.2, y=-0.5)
    return player


p1 = create_human_player(color.azure, (-FIELD_HALF_X*0.6, PLAYER_H/2, 0))

p2 = create_human_player(color.orange, (FIELD_HALF_X*0.6, PLAYER_H/2, 0))

# Front-Spieler am Netz (näher am Netz, leicht höher für Blockstellung)
p1_front = create_human_player(color.azure.tint(0.2), (-FIELD_HALF_X*0.15, PLAYER_H/2, 0))

p2_front = create_human_player(color.orange.tint(0.2), (FIELD_HALF_X*0.15, PLAYER_H/2, 0))

p1_vy = 0.0
p2_vy = 0.0
p1_front_vy = 0.0
p2_front_vy = 0.0

# ---------------------------
# Ball
# ---------------------------
BALL_R = 0.5
ball = Entity(model='sphere', color=color.yellow, scale=BALL_R*2,
              position=(-FIELD_HALF_X*0.4, 6, 0), collider='sphere', shader=None)

ball_vel = Vec3(9, 10, 0)    # Startimpuls
BALL_GRAV = -22
RESTITUTION_GROUND = 0.45     # wie „gummig“ der Boden ist
RESTITUTION_NET = 0.4
RESTITUTION_PLAYER = 1.05     # leichter Speed‑Gain beim Schlag

# Cooldown, um Mehrfachkollisionen im selben Frame zu vermeiden
ball_hit_cooldown = 0.0

# ---------------------------
# Score / Text
# ---------------------------
score_left = 0
score_right = 0
score_text = Text(text='0 : 0', origin=(0, 0), scale=2, position=(0, .45))
hint_text = Text(text='P1: WASD + SPACE | P2: Pfeile + RSHIFT', origin=(0, 0), scale=1, position=(0, .4))

# Wer serviert? -1 = links, +1 = rechts
serve_dir = -1


def clamp(v, vmin, vmax):
    return max(vmin, min(v, vmax))


def aabb_sphere_hit(box: Entity, sph: Entity, sph_r: float) -> bool:
    """Einfacher AABB-gegen-Sphäre-Test im Weltraum (ohne Rotation der Box)."""
    dx = max(abs(sph.x - box.x) - box.scale_x/2, 0)
    dy = max(abs(sph.y - box.y) - box.scale_y/2, 0)
    dz = max(abs(sph.z - box.z) - box.scale_z/2, 0)
    return (dx*dx + dy*dy + dz*dz) < (sph_r * sph_r)


def reset_rally(point_for_right: bool):
    """Punktestand anpassen und Ball/Spieler zurücksetzen."""
    global score_left, score_right, serve_dir, ball_vel, p1_vy, p2_vy
    if point_for_right:
        score_right += 1
        serve_dir = -1  # gegnerischer Aufschlag
    else:
        score_left += 1
        serve_dir = 1

    score_text.text = f'{score_left} : {score_right}'

    # Spieler zurück
    p1.position = (-FIELD_HALF_X*0.6, PLAYER_H/2, 0)
    p2.position = ( FIELD_HALF_X*0.6, PLAYER_H/2, 0)
    p1_vy = 0
    p2_vy = 0

    # Ball auf Aufschlagseite hoch und leicht nach drüben
    bx = -FIELD_HALF_X*0.4 if serve_dir == -1 else FIELD_HALF_X*0.4
    ball.position = (bx, 6, 0)
    ball_vel = Vec3(8 * serve_dir, 10, 0)


def handle_player_movement():
    """Seit-/Tiefenbewegung + Springen für beide Spieler."""
    global p1_vy, p2_vy

    dt = time.dt

    # --- Spieler 1 (links): WASD, SPACE ---
    move_p1 = Vec3(0, 0, 0)
    if held_keys['a']: move_p1.x -= 1
    if held_keys['d']: move_p1.x += 1
    if held_keys['w']: move_p1.z += 1
    if held_keys['s']: move_p1.z -= 1
    if move_p1.length() > 0:
        move_p1 = move_p1.normalized() * MOVE_SPEED * dt

    p1.x += move_p1.x
    p1.z += move_p1.z

    # Grenzen: linke Feldhälfte
    p1.x = clamp(p1.x, -FIELD_HALF_X + PLAYER_W/2, -NET_THICKNESS/2 - PLAYER_W/2)
    p1.z = clamp(p1.z, -FIELD_HALF_Z + PLAYER_D/2, FIELD_HALF_Z - PLAYER_D/2)

    # einfache Bodenprüfung
    on_ground_p1 = p1.y <= PLAYER_H/2 + 1e-3
    if on_ground_p1:
        p1.y = PLAYER_H/2
        if held_keys['space']:
            p1_vy = JUMP_FORCE
        else:
            p1_vy = max(0, p1_vy)  # kein weiteres Absinken

    p1_vy += PLAYER_GRAV * dt
    p1.y += p1_vy * dt
    if p1.y < PLAYER_H/2:
        p1.y = PLAYER_H/2

    # --- Spieler 2 (rechts): Pfeiltasten, RSHIFT ---
    move_p2 = Vec3(0, 0, 0)
    if held_keys['left arrow']:  move_p2.x -= 1
    if held_keys['right arrow']: move_p2.x += 1
    if held_keys['up arrow']:    move_p2.z += 1
    if held_keys['down arrow']:  move_p2.z -= 1
    if move_p2.length() > 0:
        move_p2 = move_p2.normalized() * MOVE_SPEED * dt

    p2.x += move_p2.x
    p2.z += move_p2.z

    # Grenzen: rechte Feldhälfte
    p2.x = clamp(p2.x, NET_THICKNESS/2 + PLAYER_W/2, FIELD_HALF_X - PLAYER_W/2)
    p2.z = clamp(p2.z, -FIELD_HALF_Z + PLAYER_D/2, FIELD_HALF_Z - PLAYER_D/2)

    on_ground_p2 = p2.y <= PLAYER_H/2 + 1e-3
    if on_ground_p2:
        p2.y = PLAYER_H/2
        if held_keys['right shift'] or held_keys['shift']:   # manche Tastaturen melden 'shift'
            p2_vy = JUMP_FORCE
        else:
            p2_vy = max(0, p2_vy)

    p2_vy += PLAYER_GRAV * dt
    p2.y += p2_vy * dt
    if p2.y < PLAYER_H/2:
        p2.y = PLAYER_H/2


def reflect_from_player(player: Entity, extra_power: float):
    """Ballprall vom Spieler mit einfacher Richtungsschätzung + optionalem Schlag-Boost."""
    global ball_vel
    # Richtung vom Spielerzentrum zum Ball
    hit_dir = (ball.world_position - player.world_position)
    hit_dir.y = max(hit_dir.y, 0.3)  # kleine Mindestanhebung
    if hit_dir.length() == 0:
        hit_dir = Vec3(0.5, 1, 0)
    hit_dir = hit_dir.normalized()

    speed = max(12, ball_vel.length() * 0.9 + 8) + extra_power
    ball_vel = hit_dir * speed

    # kleine seitliche Zufälligkeit (ohne random; deterministisch via Vorzeichenwechsel)
    ball_vel.z += 0.5 * copysign(1, (player.x + player.z) or 1)


def send_to_front_player(front_player: Entity):
    """Schicke Ball zum Front-Spieler (Zuspiel zum Netzangriff)."""
    global ball_vel
    # Richtung vom hinteren Spieler zum Front-Spieler, dann schräg nach oben
    target_dir = (front_player.world_position - ball.world_position)
    target_dir.y = 3.5  # viel steiler nach oben für höheres Zuspiel
    if target_dir.length() > 0:
        target_dir = target_dir.normalized()
    
    speed = 13  # schneller Pass
    ball_vel = target_dir * speed


def update():
    global ball_vel, ball_hit_cooldown

    dt = time.dt

    # Spieler bewegen
    handle_player_movement()

    # Ball Physik
    ball_vel.y += BALL_GRAV * dt
    ball.position += ball_vel * dt

    # Spielfeldbegrenzungen (Z- und X-Wände, aber nicht über das Netz in X)
    # Rückwände Z
    if ball.z < -FIELD_HALF_Z + BALL_R:
        ball.z = -FIELD_HALF_Z + BALL_R
        ball_vel.z *= -0.7
    if ball.z > FIELD_HALF_Z - BALL_R:
        ball.z = FIELD_HALF_Z - BALL_R
        ball_vel.z *= -0.7

    # Seitenlinien in X (ganz außen)
    if ball.x < -FIELD_HALF_X + BALL_R:
        ball.x = -FIELD_HALF_X + BALL_R
        ball_vel.x *= -0.7
    if ball.x > FIELD_HALF_X - BALL_R:
        ball.x = FIELD_HALF_X - BALL_R
        ball_vel.x *= -0.7

    # Boden
    if ball.y <= BALL_R:
        # Punkt: Welche Seite berührt?
        left_side = ball.x < 0
        ball.y = BALL_R
        # kurzer Bounce-Effekt (damit man es sieht)
        ball_vel.y *= -RESTITUTION_GROUND
        ball_vel.x *= 0.85
        ball_vel.z *= 0.85

        # Punkt vergeben & Rally resetten
        if left_side:
            reset_rally(point_for_right=True)
        else:
            reset_rally(point_for_right=False)

    # Netz-Kollision (einfacher AABB-Sphere-Test)
    if aabb_sphere_hit(net, ball, BALL_R):
        # Prall an der Netzfläche
        # Wenn von links -> nach links reflektieren usw.
        side = -1 if ball.x < 0 else 1
        ball.x = side * (NET_THICKNESS/2 + BALL_R)
        ball_vel.x *= -RESTITUTION_NET
        ball_vel.y *= 0.95
        ball_vel.z *= 0.95

    # Spieler-Kollision (mit kleinem Cooldown)
    ball_hit_cooldown = max(0.0, ball_hit_cooldown - dt)
    def try_hit(player: Entity, front_player: Entity, hit_key_held: bool):
        global ball_hit_cooldown
        if ball_hit_cooldown > 0:
            return
        if aabb_sphere_hit(player, ball, BALL_R):
            # Hinterer Spieler trifft -> Ball zum Front-Spieler
            send_to_front_player(front_player)
            ball_hit_cooldown = 0.12  # 120 ms Sperre

    def try_hit_front(front_player: Entity, hit_key_held: bool):
        global ball_hit_cooldown
        if ball_hit_cooldown > 0:
            return
        if aabb_sphere_hit(front_player, ball, BALL_R):
            # Front-Spieler trifft -> normaler Prall mit Extra-Power
            extra = 6.0 if hit_key_held else 2.0
            reflect_from_player(front_player, extra_power=extra)
            ball_hit_cooldown = 0.12

    try_hit(p1, p1_front, held_keys['space'])
    try_hit(p2, p2_front, held_keys['right shift'] or held_keys['shift'])
    # Front-Spieler können auch treffen (optional, ohne extra Keys)
    try_hit_front(p1_front, False)
    try_hit_front(p2_front, False)


app.run()