# Enable modern Python type features so our code runs cleanly and consistently

from __future__ import annotations



# Built-in tool to read and write JSON files (which store the bot's learned memory)

import json

# Built-in tool for geometry and trigonometry (distances, angles, square roots)

import math

# Built-in tool for making random choices and rolling virtual dice

import random

# Built-in tool to navigate files and folders on your computer

from pathlib import Path

# Built-in tool for generic type annotations

from typing import Any





# A dictionary mapping each compass direction name to its (X, Y) movement steps on the grid

# (0, 0) means stay still; (0, 1) means move 1 step up toward the top of the field

DIRECTION_VECTORS = {

    # Compass directional coordinate: "STAY": (0, 0),

    "STAY": (0, 0),

    # Compass directional coordinate: "UP": (0, 1),

    "UP": (0, 1),

    # Compass directional coordinate: "UP_RIGHT": (1, 1),

    "UP_RIGHT": (1, 1),

    # Compass directional coordinate: "RIGHT": (1, 0),

    "RIGHT": (1, 0),

    # Compass directional coordinate: "DOWN_RIGHT": (1, -1),

    "DOWN_RIGHT": (1, -1),

    # Compass directional coordinate: "DOWN": (0, -1),

    "DOWN": (0, -1),

    # Compass directional coordinate: "DOWN_LEFT": (-1, -1),

    "DOWN_LEFT": (-1, -1),

    # Compass directional coordinate: "LEFT": (-1, 0),

    "LEFT": (-1, 0),

    # Compass directional coordinate: "UP_LEFT": (-1, 1),

    "UP_LEFT": (-1, 1),

# End of direction vector mapping

}

# A simple list of all 9 possible movement choices our player can make

MOVES = list(DIRECTION_VECTORS)

# A list of the 8 directions we can kick the ball (we cannot kick while staying still)

KICK_DIRECTIONS = [name for name in MOVES if name != "STAY"]

# Total unique actions the policy can choose from: 9 moves + (8 kick directions * 3 power levels) = 33 actions

ACTION_COUNT = len(MOVES) + len(KICK_DIRECTIONS) * 3





# Helper function: figures out which compass direction to face to walk toward a target point (dx, dy)

def direction_toward(dx: float, dy: float, dead_zone: float = 1.0) -> str:

    # If horizontal distance is tiny (within dead_zone), don't turn left or right; otherwise pick RIGHT or LEFT

    horizontal = "" if abs(dx) <= dead_zone else ("RIGHT" if dx > 0 else "LEFT")

    # If vertical distance is tiny, don't turn up or down; otherwise pick UP or DOWN

    vertical = "" if abs(dy) <= dead_zone else ("UP" if dy > 0 else "DOWN")

    # Combine vertical and horizontal (like "UP_RIGHT"); if only one, return that; if neither, return "STAY"

    return f"{vertical}_{horizontal}" if vertical and horizontal else vertical or horizontal or "STAY"





# Helper function: takes a continuous number (like distance in meters) and sorts it into a simple category box (bucket)

def _bucket(value: float, limits: tuple[float, ...]) -> int:

    # Find the first cutoff limit that our number is smaller than, and return its bucket index number

    return next((index for index, limit in enumerate(limits) if value < limit), len(limits))





# Helper function: slices the 360-degree circle around our player into 8 pizza slices (sectors) to know where something is

def _sector(dx: float, dy: float) -> int:

    # If the object is right on top of us, assign it to a special "neutral" sector 8

    if abs(dx) + abs(dy) < 1e-9:

        # Return calculated outcome: return 8

        return 8

    # Calculate the angle using atan2, divide into 45-degree slices, and wrap around from 0 to 7

    return int(round(math.atan2(dy, dx) / (math.pi / 4))) % 8





# Helper function: tests if stepping in a specific direction is safe (won't crash into a wall or obstacle)

def _move_is_safe(observation: dict[str, Any], move: str) -> bool:

    # Standing still is always safe because you won't crash into anything new

    if move == "STAY":

        # Return calculated outcome: return True

        return True

    # Look at the current state of the field

    state = observation["state"]

    # Look at our own player's current position and dimensions

    me = state["players"][observation["player_id"]]

    # Execute operational logic: field = state["field"]

    field = state["field"]

    # How fast our player walks in one tick (default 4.0 units)

    speed = float(field.get("player_speed", 4.0))

    # Our player's body radius (default 3.0 units)

    radius = float(field.get("player_radius", 3.0))

    # Get the step vector for this direction (e.g. (1, 1) for UP_RIGHT)

    vx, vy = DIRECTION_VECTORS[move]

    # Calculate the vector length so diagonal steps don't move faster than straight steps

    length = math.hypot(vx, vy) or 1.0

    # Calculate where our player's X coordinate WOULD be if we took this step

    x = me["x"] + vx / length * speed

    # Calculate where our player's Y coordinate WOULD be if we took this step

    y = me["y"] + vy / length * speed

    # Check if this new position pushes our body outside the left, right, bottom, or top boundary walls

    if x - radius < 0 or x + radius > field["width"] or y - radius < 0 or y + radius > field["height"]:

        # Unsafe! We would hit an outer boundary wall

        return False

    # Check every solid obstacle box on the field

    for obstacle in state.get("obstacles", []):

        # Find the point on the obstacle rectangle that is closest to our player's center

        closest_x = min(max(x, obstacle["x"]), obstacle["x"] + obstacle["width"])

        # Execute operational logic: closest_y = min(max(y, obstacle["y"]), obstacle["y"] + obstacle["height"])

        closest_y = min(max(y, obstacle["y"]), obstacle["y"] + obstacle["height"])

        # If the distance from our center to the obstacle is smaller than our radius, we would crash!

        if math.hypot(x - closest_x, y - closest_y) < radius + 0.25:

            # Unsafe! We would hit an obstacle

            return False

    # Safe! No walls or obstacles in the way

    return True





# Helper function: takes the move we WANT to make, and if it is blocked, picks the closest legal alternative direction

def _safe_move(observation: dict[str, Any], preferred: str) -> str:

    # If the preferred move is to stay still and that's safe, hold our ground

    if preferred == "STAY":

        # Return calculated outcome: return "STAY"

        return "STAY"

    # Look up the movement vector of our desired direction

    preferred_vector = DIRECTION_VECTORS[preferred]

    # Filter the list of 9 moves to only keep moves that don't hit walls or obstacles

    choices = [move for move in MOVES if move != "STAY" and _move_is_safe(observation, move)]

    # If every single direction is blocked (e.g. cornered), our only choice is to STAY still

    if not choices:

        # Return calculated outcome: return "STAY"

        return "STAY"

    # Look up player coordinates to break lateral ties toward the open center of the pitch (X=50.0)

    me_x = float(observation["state"]["players"][observation["player_id"]]["x"])

    # Look up team attacking direction to determine which vertical direction retreats toward our defending goal

    retreat_dy = -1.0 if observation.get("attack_direction", "UP") == "UP" else 1.0

    # Pick the legal move: prioritize desired move, total directional alignment, vertical goal-side retreat, then pitch center

    return max(

        # Execute operational logic: choices,

        choices,

        # Execute operational logic: key=lambda move: (

        key=lambda move: (

            # Execute operational logic: move == preferred,

            move == preferred,

            # Execute operational logic: DIRECTION_VECTORS[move][0] * preferred_vector[0] + DIRECTION_VECTORS[move][1] * preferred_vector[1],

            DIRECTION_VECTORS[move][0] * preferred_vector[0] + DIRECTION_VECTORS[move][1] * preferred_vector[1],

            # Vertical alignment with preferred move, falling back to defensive goal-side retreat when preferred move is purely lateral

            DIRECTION_VECTORS[move][1] * preferred_vector[1] if preferred_vector[1] != 0 else DIRECTION_VECTORS[move][1] * retreat_dy,

            # Execute operational logic: -DIRECTION_VECTORS[move][0] * (me_x - 50.0),

            -DIRECTION_VECTORS[move][0] * (me_x - 50.0),

        # Execute operational logic: ),

        ),

    # Execute operational logic: )

    )



# Helper function: tests if a kick in a given direction would hit an obstacle within 20 units

def _kick_hits_obstacle(state: dict[str, Any], x: float, y: float, direction: str) -> bool:

    # Look up step vector for the given kick direction

    vx, vy = DIRECTION_VECTORS.get(direction, (0, 0))

    # Normalize length so diagonal checks travel at consistent speed

    length = math.hypot(vx, vy) or 1.0

    # Calculate unit directional offsets

    dx, dy = vx / length, vy / length

    # Check sample points along the ball's flight path every 4 units up to 20 units

    for dist in (4.0, 8.0, 12.0, 16.0, 20.0):

        # Calculate simulated ball coordinate

        tx, ty = x + dx * dist, y + dy * dist

        # Check against every static obstacle block on the field

        for obs in state.get("obstacles", []):

            # If the ball trajectory intersects the obstacle rectangle

            if obs["x"] - 1.0 <= tx <= obs["x"] + obs["width"] + 1.0 and obs["y"] - 1.0 <= ty <= obs["y"] + obs["height"] + 1.0:

                # Obstacle is directly blocking this kick!

                return True

    # The kick path is completely clear

    return False





# Helper function: tests if a kick in a given direction would hit an opponent within 24 units

def _kick_hits_opponent(me_x: float, me_y: float, opp_x: float, opp_y: float, direction: str) -> bool:

    # Look up step vector for the given kick direction

    vx, vy = DIRECTION_VECTORS.get(direction, (0, 0))

    # Normalize length so diagonal checks travel at consistent speed

    length = math.hypot(vx, vy) or 1.0

    # Calculate unit directional offsets

    dx, dy = vx / length, vy / length

    # Check sample points along the ball's flight path every 3 units up to 24 units

    for dist in (3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0, 24.0):

        # Calculate simulated ball coordinate

        tx, ty = me_x + dx * dist, me_y + dy * dist

        # If the ball passes within 7.5 units of the opponent's body (accounting for tackle radius and opponent speed)

        if math.hypot(tx - opp_x, ty - opp_y) < 7.5:

            # Kick would pass right into the opponent's tackle zone!

            return True

    # The kick path does not hit the opponent

    return False





# Tactical decision engine: Dynamic 8-Legend persona-switching architecture (Lev Yashin, Paolo Maldini,

# Franz Beckenbauer, Cafu, Lothar Matthäus, Diego Maradona, Lionel Messi, Pelé)

def tactical_action(observation: dict[str, Any], kick_power: int = 3) -> dict[str, Any]:

    # Extract our bot's unique player identification string ('player_1' or 'player_2')

    player_id = observation["player_id"]

    # Extract the other bot's unique player identification string

    opponent_id = observation["opponent_id"]

    # Access the complete simulator state containing all pitch entities

    state = observation["state"]

    # Access stadium dimensions such as pitch width and pitch length

    field = state["field"]

    # Look up our own player's current coordinate and body details

    me = state["players"][player_id]

    # Look up the opponent's current coordinate and body details

    opponent = state["players"][opponent_id]

    # Look up the ball's current location, speed, and possession status

    ball = state["ball"]

    # Check whether we are trying to score by moving UP (+Y) or DOWN (-Y)

    attack = observation["attack_direction"]

    # Convert direction into a multiplier: +1 when going UP, -1 when going DOWN

    sign = 1 if attack == "UP" else -1

    # Get total stadium width from touchline to touchline (100 units)

    field_width = float(field["width"])

    # Get total stadium length from goal line to goal line (140 units)

    field_height = float(field["height"])

    # Calculate the Y coordinate of the goal net we must protect (0 if attacking UP, 140 if attacking DOWN)

    defend_goal_y = 0.0 if sign > 0 else field_height

    # Calculate the Y coordinate of the goal net we are attacking to score

    target_goal_y = field_height if sign > 0 else 0.0



    # =========================================================================

    # SITUATION 1: OUR BOT CONTROLS THE BALL (Offense / Attacking Personas)

    # =========================================================================

    if ball["possession"] == player_id:

        # Distance remaining in straight units to the opponent's goal line

        distance_to_goal = field_height - me["y"] if sign > 0 else me["y"]

        # How many consecutive simulation ticks our bot has held onto the ball

        possession_steps = int(ball.get("possession_steps", 0))



        # Horizontal distance between our bot and the defending opponent

        dx_opp = opponent["x"] - me["x"]

        # Vertical distance toward the opponent along our attacking axis

        dy_opp = sign * (opponent["y"] - me["y"])

        # Direct straight-line Euclidean distance between our bot and the defender

        dist_opp = math.hypot(dx_opp, dy_opp)

        # Check if the defender is standing in front of us within pressing distance (under 18 units)

        opponent_blocking = dy_opp > 0 and abs(dx_opp) < 12.0 and dist_opp < 18.0



        # Diego Maradona Persona: If defender is closing head-on, evade with a sharp lateral V-cut

        if me["x"] <= 15.0:

            # When pinned to the left touchline, always cut inside to the right into open pitch space

            evade_side = "RIGHT"

        # Alternative branch condition: elif me["x"] >= 85.0:

        elif me["x"] >= 85.0:

            # When pinned to the right touchline, always cut inside to the left into open pitch space

            evade_side = "LEFT"

        # Alternative branch condition: else:

        else:

            # In the open field, dodge to whichever side the defender is not covering

            evade_side = "LEFT" if dx_opp >= 0 else "RIGHT"

            # If the preferred dodge direction is blocked by an obstacle, cut to the opposite open side

            if not _move_is_safe(observation, evade_side):

                # Reverse evasion side when the preferred flank is obstructed

                evade_side = "RIGHT" if evade_side == "LEFT" else "LEFT"

        # Combine attacking drive with side step to bypass the defender's tackle zone

        dribble_evade = f"{attack}_{evade_side}" if opponent_blocking else attack

        # If opponent is blocking us head-on: in close range (dist_opp < 12.0), take a pure lateral cut to dodge tackle; otherwise take forward diagonal cut

        if opponent_blocking:

            # When defender is dangerously close, take a pure lateral side-step to avoid charging into their tackle radius

            primary_evade = evade_side if dist_opp < 12.0 else f"{attack}_{evade_side}"

            # Secondary evasion direction if primary is blocked by an obstacle

            secondary_evade = f"{attack}_{evade_side}" if primary_evade == evade_side else evade_side

            # Check if primary evasion path is safe

            if _move_is_safe(observation, primary_evade):

                # Execute operational logic: move = primary_evade

                move = primary_evade

            # Check if secondary evasion path is safe

            elif _move_is_safe(observation, secondary_evade):

                # Execute operational logic: move = secondary_evade

                move = secondary_evade

            # Alternative branch condition: else:

            else:

                # Steer around the obstacle with safe move fallback

                move = _safe_move(observation, evade_side)

        # Alternative branch condition: else:

        else:

            # Pick the safest legal direction that avoids colliding with obstacles or touchline walls

            move = _safe_move(observation, dribble_evade)



        # Preemptor Safety Rule: The game engine enforces a turnover kick if held for 10 ticks, so shoot by tick 8

        must_release = possession_steps >= 8



        # Cafu Persona (The Flank Cutback Specialist): When pinned deep on either flank touchline

        is_deep_flank = (me["x"] >= 72.0 or me["x"] <= 28.0) and distance_to_goal < 32.0

        # Decision branch condition: if is_deep_flank:

        if is_deep_flank:

            # Shooting from extreme flank angles hits the solid back wall outside the 34-to-66 goal mouth

            target_cutback_x = 50.0

            # Target the central edge of the penalty box to set up central finishes and dangerous rebounds

            target_cutback_y = target_goal_y - sign * 20.0

            # Aim inward cross into open space

            direction = direction_toward(target_cutback_x - me["x"], target_cutback_y - me["y"], dead_zone=3.0)

            # Fetch allowed kick power options

            powers = observation["action_space"]["kick"]["power"]

            # Power 2 delivers crisp pass speed without over-hitting out of bounds

            power = 2 if 2 in powers else min(powers)

            # Deliver the cutback cross and step inside toward center

            cutback_move = _safe_move(observation, "LEFT" if me["x"] >= 50.0 else "RIGHT")

            # Return calculated outcome: return {"move": cutback_move, "kick": {"direction": direction, "power": power}}

            return {"move": cutback_move, "kick": {"direction": direction, "power": power}}



        # Pelé Persona (The Clinical Kill Box Finisher): Inside 35 units of goal, shoot with zero delay

        in_kill_box = distance_to_goal <= 35.0

        # Decision branch condition: if in_kill_box:

        if in_kill_box:

            # Pelé Rule: Pick the open corner furthest away from where the opposing goalkeeper is standing

            aim_x = 63.5 if opponent["x"] < 50.0 else 36.5

            # Aim straight at that open corner inside the goal mouth (between 34 and 66)

            direction = direction_toward(aim_x - me["x"], sign * distance_to_goal, dead_zone=2.0)

            # Verify if this compass direction actually hits inside the 34-to-66 goal mouth

            vx_kick, vy_kick = DIRECTION_VECTORS[direction]

            # Ensure shot travels forward toward the goal line

            if sign * vy_kick > 0:

                # Calculate where this kick crosses the goal line

                x_at_net = me["x"] + (vx_kick / vy_kick) * (target_goal_y - me["y"])

                # If the shot would hit the solid back wall outside the posts, aim straight forward instead

                if not (33.0 <= x_at_net <= 67.0):

                    # Execute operational logic: direction = attack

                    direction = attack

            # Fetch allowed kick power options from simulator action space

            powers = observation["action_space"]["kick"]["power"]

            # Power 2 delivers crisp precision inside the penalty box

            power = 2 if 2 in powers else min(powers)

            # Execute the strike immediately into the open corner

            return {"move": move, "kick": {"direction": direction, "power": power}}



        # Lionel Messi Persona (Inverted Winger & Far-Post Curled Finish): Distance between 35 and 58 units

        in_messi_zone = distance_to_goal <= 58.0 or must_release

        # Decision branch condition: if in_messi_zone:

        if in_messi_zone:

            # Lionel Messi Far-Post Geometry: If attacking from the left channel, curl shot to far-right post (63.5)

            if me["x"] < 47.0:

                # Execute operational logic: aim_x = 63.5

                aim_x = 63.5

            # If attacking from the right channel, curl shot across keeper to far-left post (36.5)

            elif me["x"] > 53.0:

                # Execute operational logic: aim_x = 36.5

                aim_x = 36.5

            # Otherwise aim directly at the center of the net (50.0)

            else:

                # Execute operational logic: aim_x = 50.0

                aim_x = 50.0

            # If defender is in our shooting lane, prioritize dribbling around them; otherwise strike at target

            direction = dribble_evade if opponent_blocking else direction_toward(

                # Execute operational logic: aim_x - me["x"], sign * distance_to_goal, dead_zone=3.0

                aim_x - me["x"], sign * distance_to_goal, dead_zone=3.0

            # Execute operational logic: )

            )

            # Fetch allowed kick power options

            powers = observation["action_space"]["kick"]["power"]

            # Unleash maximum power on the far-post shot

            power = min(max(powers), max(min(powers), kick_power))

            # Return movement step and goal shot

            return {"move": move, "kick": {"direction": direction, "power": power}}



        # Lothar Matthäus Persona (The Midfield Cannon Rocket): Distance between 45 and 75 units with open line of sight

        if 45.0 <= distance_to_goal <= 75.0 and not opponent_blocking:

            # Aim for the corner post opposite to where defender is positioned

            aim_x = 63.5 if opponent["x"] < 50.0 else 36.5

            # Direct rocket toward that post pocket

            direction = direction_toward(aim_x - me["x"], sign * distance_to_goal, dead_zone=4.0)

            # Fetch allowed kick power options

            powers = observation["action_space"]["kick"]["power"]

            # Maximum Power 3 reaches 85 units to blast past the keeper from downtown

            power = max(powers)

            # Unleash the Matthäus cannon shot

            return {"move": move, "kick": {"direction": direction, "power": power}}



        # Franz Beckenbauer Persona (The Sweeper Out of Defense): In our own defensive half (distance > 65.0)

        if distance_to_goal > 65.0:

            # Under-pressure check: Is an opponent within dangerous tackling range (under 14 units) from any direction?

            under_pressure = opponent_blocking or dist_opp < 14.0

            # Rule 1: Safe Carrying only when genuinely unpressured!

            if not under_pressure and possession_steps < 5:

                # Carry forward with speed to penetrate into the final third

                return {"move": move}

            # Rule 2: Dribble Immunity Protection when pressured (first 2 ticks to align clearance)

            if possession_steps < 2:

                # Carry the ball smoothly around any pressing defenders without kicking directly into them

                return {"move": move}

            # Rule 3: Safe Flank Clearance! When pressured by a defender, clear along the open channel

            if abs(dx_opp) < 14.0 and dy_opp > 0:

                # If defender is directly in our forward clearing lane, bypass them diagonally down the open wing

                clear_direction = f"{attack}_LEFT" if opponent["x"] >= 50.0 else f"{attack}_RIGHT"

            # Alternative branch condition: else:

            else:

                # Calculate clearance direction toward pitch center or evasion vector

                clear_direction = dribble_evade if opponent_blocking else direction_toward(50.0 - me["x"], sign * distance_to_goal, dead_zone=4.0)

            # If on touchline flanks, ensure clearance directs away from the side wall into the pitch center

            if me["x"] <= 20.0:

                # On the left flank, direct the clearance toward the open central right channel

                clear_direction = f"{attack}_RIGHT"

            # Alternative branch condition: elif me["x"] >= 80.0:

            elif me["x"] >= 80.0:

                # On the right flank, direct the clearance toward the open central left channel

                clear_direction = f"{attack}_LEFT"

            # Obstacle & Opponent Safety Check: Never kick straight into an obstacle or opponent!

            opp_x, opp_y = opponent["x"], opponent["y"]

            # Execute operational logic: kick_blocked = _kick_hits_obstacle(state, me["x"], me["y"], clear_direction) or _kick_hits_opponent(me["x"], me["y"], opp_x, opp_y, clear_direction)

            kick_blocked = _kick_hits_obstacle(state, me["x"], me["y"], clear_direction) or _kick_hits_opponent(me["x"], me["y"], opp_x, opp_y, clear_direction)

            # Decision branch condition: if kick_blocked:

            if kick_blocked:

                # Try the opposite forward diagonal flank to bypass the obstacle/opponent

                alt_direction = f"{attack}_RIGHT" if "LEFT" in clear_direction else f"{attack}_LEFT"

                # If opposite diagonal is open, clear that way!

                if not (_kick_hits_obstacle(state, me["x"], me["y"], alt_direction) or _kick_hits_opponent(me["x"], me["y"], opp_x, opp_y, alt_direction)):

                    # Execute operational logic: clear_direction = alt_direction

                    clear_direction = alt_direction

                # Alternative branch condition: else:

                else:

                    # If both diagonals are blocked, try straight forward down the middle

                    if not (_kick_hits_obstacle(state, me["x"], me["y"], attack) or _kick_hits_opponent(me["x"], me["y"], opp_x, opp_y, attack)):

                        # Execute operational logic: clear_direction = attack

                        clear_direction = attack

                    # Alternative branch condition: else:

                    else:

                        # If all forward kicks hit obstacles or opponents, carry laterally rather than causing a turnover!

                        return {"move": move}

            # Fetch allowed kick power options

            powers = observation["action_space"]["kick"]["power"]

            # Clear with maximum power so the ball sails safely into the opponent's half

            power = max(powers)

            # Step and clear the ball

            return {"move": move, "kick": {"direction": clear_direction, "power": power}}



        # Midfield carrying when open: advance into shooting range (up to 5 steps of possession)

        if distance_to_goal > 45.0 and possession_steps < 5 and not opponent_blocking:

            # Carry forward with speed to penetrate into the final third

            return {"move": move}



        # General forward transition kick: aim toward the open corner furthest away from the defender

        aim_x = 63.5 if opponent["x"] < 50.0 else 36.5

        # If the opponent is directly in our forward shooting lane, curve the kick around them down the wing

        if abs(dx_opp) < 14.0 and dy_opp > 0:

            # Kick down the opposite flank to prevent central turnovers

            direction = f"{attack}_LEFT" if opponent["x"] >= 50.0 else f"{attack}_RIGHT"

        # Alternative branch condition: else:

        else:

            # Calculate compass direction toward open corner avoiding defenders

            direction = dribble_evade if opponent_blocking else direction_toward(aim_x - me["x"], sign * distance_to_goal, dead_zone=4.0)

        # Fetch allowed kick power options

        powers = observation["action_space"]["kick"]["power"]

        # Use full power for long clearances

        power = min(max(powers), max(min(powers), kick_power))

        # Step forward and kick the ball

        return {"move": move, "kick": {"direction": direction, "power": power}}



    # =========================================================================

    # SITUATION 2: BALL IS LOOSE OR ENEMY HAS IT (Defense & Goalkeeping)

    # =========================================================================

    # Access the ball's current movement velocity dictionary

    velocity = ball.get("velocity", {})

    # Horizontal velocity speed of the ball (units per simulation tick)

    vx = float(velocity.get("x", 0.0))

    # Vertical velocity speed of the ball (units per simulation tick)

    vy = float(velocity.get("y", 0.0))



    # Lev Yashin Persona (The Black Spider Shot-Stopper): Intercept fast balls flying toward our net

    is_incoming = (sign > 0 and vy < -1.5) or (sign < 0 and vy > 1.5)

    # Only calculate shot trajectory if the ball is actively moving at speed

    if is_incoming and ball["status"] == "moving":

        # Simulate full multi-bounce trajectory up to 35 ticks into the future

        curr_sim_x, curr_sim_y = float(ball["x"]), float(ball["y"])

        # Track horizontal ball velocity across potential wall reflections

        curr_sim_vx = vx

        # Track vertical ball velocity across potential back wall rebounds

        curr_sim_vy = vy

        # Store the earliest coordinate where our bot can physically intercept the shot in flight

        intercept_target = None

        # Store the horizontal coordinate where the ball crosses or rebounds near our goal line

        goal_mouth_target_x = 50.0

        # Radius of the ball for physical wall rebound calculations

        sim_ball_radius = 1.5

        # Forward simulation loop across future ticks

        for step in range(1, 35):

            # Advance simulated ball position horizontally

            curr_sim_x += curr_sim_vx

            # Advance simulated ball position vertically

            curr_sim_y += curr_sim_vy

            # Reflect horizontal velocity if the ball bounces off left touchline wall

            if curr_sim_x - sim_ball_radius < 0.0:

                # Invert horizontal flight direction

                curr_sim_vx = -curr_sim_vx

                # Clamp horizontal coordinate safely within touchline

                curr_sim_x = min(max(curr_sim_x, sim_ball_radius), field_width - sim_ball_radius)

            # Reflect horizontal velocity if the ball bounces off right touchline wall

            elif curr_sim_x + sim_ball_radius > field_width:

                # Invert horizontal flight direction

                curr_sim_vx = -curr_sim_vx

                # Clamp horizontal coordinate safely within touchline

                curr_sim_x = min(max(curr_sim_x, sim_ball_radius), field_width - sim_ball_radius)

            # Check if ball strikes the bottom back wall or enters bottom net mouth

            if curr_sim_y - sim_ball_radius < 0.0:

                # If ball enters our defending goal mouth, record crossing coordinate

                if 34.0 <= curr_sim_x <= 66.0 and sign > 0:

                    # Goal-line crossing location

                    goal_mouth_target_x = curr_sim_x

                    # Break simulation once shot enters net

                    break

                # Reflect vertical flight direction off solid corner back wall

                curr_sim_vy = -curr_sim_vy

                # Clamp coordinate safely above back wall

                curr_sim_y = min(max(curr_sim_y, sim_ball_radius), field_height - sim_ball_radius)

            # Check if ball strikes the top back wall or enters top net mouth

            elif curr_sim_y + sim_ball_radius > field_height:

                # If ball enters our defending goal mouth, record crossing coordinate

                if 34.0 <= curr_sim_x <= 66.0 and sign < 0:

                    # Goal-line crossing location

                    goal_mouth_target_x = curr_sim_x

                    # Break simulation once shot enters net

                    break

                # Reflect vertical flight direction off solid corner back wall

                curr_sim_vy = -curr_sim_vy

                # Clamp coordinate safely below back wall

                curr_sim_y = min(max(curr_sim_y, sim_ball_radius), field_height - sim_ball_radius)

            # Check if our bot can sprint to intercept the ball at this future tick in open pitch

            if intercept_target is None:

                # Distance from our bot to this future ball coordinate

                dist_to_intercept = math.hypot(curr_sim_x - me["x"], curr_sim_y - me["y"])

                # Reach calculation: player movement speed (4.0 units/tick) plus physical possession radius (5.0 units)

                max_reach = 4.0 * step + 5.0

                # Intercept if physically reachable and located safely inside pitch boundaries

                if dist_to_intercept <= max_reach and 0.0 <= curr_sim_x <= field_width and 0.0 <= curr_sim_y <= field_height:

                    # Save first valid interception coordinates

                    intercept_target = (curr_sim_x, curr_sim_y)

            # Check if ball has reached the defensive goal line threshold

            if (sign > 0 and curr_sim_y <= 4.5) or (sign < 0 and curr_sim_y >= field_height - 4.5):

                # Record horizontal position where ball arrives at our goal line

                goal_mouth_target_x = curr_sim_x

                # Stop forward simulation once goal line plane is reached

                break

        # If a clean open-pitch interception is possible, sprint directly toward the cut-off point

        if intercept_target is not None:

            # Steer directly toward the interception point

            preferred = direction_toward(intercept_target[0] - me["x"], intercept_target[1] - me["y"], dead_zone=0.5)

            # Execute mid-flight interception step

            return {"move": _safe_move(observation, preferred)}

        # Yashin Rule: Anchor within the 35-to-65 goal mouth to block direct shots and solid-wall ricochets

        target_x = max(35.0, min(65.0, goal_mouth_target_x))

        # Position our body 4.5 units in front of the line so we don't get trapped on the back wall

        target_y = defend_goal_y + sign * 4.5

        # Check obstacles to detect any obstacle standing directly in our downward drop path

        player_radius = float(state.get("field", {}).get("player_radius", 3.0))

        # Inspect all solid obstacles on the pitch

        for obs in state.get("obstacles", []):

            # Vertical obstacle bounds

            obs_y_between = (obs["y"] <= me["y"] and obs["y"] + obs["height"] >= target_y) if sign > 0 else (obs["y"] + obs["height"] >= me["y"] and obs["y"] <= target_y)

            # Horizontal overlap with obstacle including player body buffer

            obs_x_between = (obs["x"] - player_radius - 1.0 <= me["x"] <= obs["x"] + obs["width"] + player_radius + 1.0)

            # If obstacle directly obstructs our vertical retreat to goal, steer toward nearest open flank

            if obs_y_between and obs_x_between:

                # Left flank coordinate around obstacle

                left_flank = obs["x"] - player_radius - 1.5

                # Right flank coordinate around obstacle

                right_flank = obs["x"] + obs["width"] + player_radius + 1.5

                # Pick the closer flank to navigate around the obstacle cleanly

                bypass_x = left_flank if abs(me["x"] - left_flank) <= abs(me["x"] - right_flank) else right_flank

                # Clamp bypass target safely inside field touchlines

                target_x = max(5.0, min(95.0, bypass_x))

                # Stop after adjusting for the blocking obstacle

                break

        # Calculate compass direction to sprint directly onto the shot trajectory

        preferred = direction_toward(target_x - me["x"], target_y - me["y"], dead_zone=1.0)

        # Execute Yashin body block save

        return {"move": _safe_move(observation, preferred)}



    # Paolo Maldini Persona (The Defensive Master): Containment, Jockeying, and Tackle Timing

    if ball["possession"] == opponent_id:

        # Check how many ticks the opponent has possessed the ball

        opp_steps = int(ball.get("possession_steps", 0))

        # Calculate physical straight-line distance from our player to the attacking opponent

        dist_to_opp = math.hypot(opponent["x"] - me["x"], opponent["y"] - me["y"])

        # Horizontal vector from opponent to the center of our defending goal line (50, defend_goal_y)

        goal_dx = 50.0 - opponent["x"]

        # Vertical vector from opponent to our defending goal line

        goal_dy = defend_goal_y - opponent["y"]

        # Total straight-line distance from opponent to our goal line

        goal_dist = math.hypot(goal_dx, goal_dy) or 1.0

        # Unit horizontal direction from opponent toward our goal center

        ux_to_goal = goal_dx / goal_dist

        # Unit vertical direction from opponent toward our goal center

        uy_to_goal = goal_dy / goal_dist



        # Maldini Axiom 1: Emergency Recovery if Opponent is Behind Us (Goal-Side Lost)

        is_behind_us = (sign > 0 and opponent["y"] < me["y"] - 1.0) or (sign < 0 and opponent["y"] > me["y"] + 1.0)

        # Decision branch condition: if is_behind_us:

        if is_behind_us:

            # Initialize target horizontal retreat coordinate to center of goal

            target_retreat_x = 50.0

            # Scan obstacles to detect any obstacle standing directly in front of defending goal mouth

            for obs in state.get("obstacles", []):

                # Check if obstacle lies between player and goal vertically near defending third

                obs_y_between = (defend_goal_y <= obs["y"] + obs["height"] and obs["y"] <= me["y"]) if sign > 0 else (me["y"] <= obs["y"] + obs["height"] and obs["y"] <= defend_goal_y)

                # Check if obstacle is located directly in front of our 34-to-66 goal mouth

                obs_in_goal_mouth = (obs["x"] < 66.0 and obs["x"] + obs["width"] > 34.0) and abs(obs["y"] - defend_goal_y) < 30.0

                # Check if obstacle lies in player's direct vertical retreat channel

                if obs_y_between and obs_in_goal_mouth and obs["x"] - 3.0 <= me["x"] <= obs["x"] + obs["width"] + 3.0:

                    # Choose the nearest flank around the obstacle to break symmetry and navigate smoothly around it

                    target_retreat_x = obs["x"] - 5.0 if me["x"] < obs["x"] + obs["width"] / 2.0 else obs["x"] + obs["width"] + 5.0

                    # Clamp flank coordinate strictly within the goal mouth channel

                    target_retreat_x = max(34.0, min(66.0, target_retreat_x))

                    # Stop after identifying the blocking obstacle

                    break

            # Sprint back at maximum speed toward our retreat target to round obstacles and regain goal-side position

            preferred = direction_toward(target_retreat_x - me["x"], defend_goal_y - me["y"], dead_zone=1.0)

            # Execute emergency defensive retreat

            return {"move": _safe_move(observation, preferred)}



        # Maldini Axiom 2: Decisive Physical Tackle Timing

        # When opponent dribble immunity has expired (opp_steps >= 3) and they are in close range (<= 4.2 units)

        if opp_steps >= 3 and dist_to_opp <= 4.2:

            # Step directly into opponent's body to win the ball cleanly

            preferred = direction_toward(opponent["x"] - me["x"], opponent["y"] - me["y"], dead_zone=0.2)

            # Execute physical tackle

            return {"move": _safe_move(observation, preferred)}



        # Maldini Axiom 3: Mid-Block Shape when Opponent is Far Upfield

        # Distance from opponent to our defending goal line

        opp_dist_from_our_goal = abs(opponent["y"] - defend_goal_y)

        # Decision branch condition: if opp_dist_from_our_goal > 60.0:

        if opp_dist_from_our_goal > 60.0:

            # Hold a compact mid-block 35 units in front of our goal net

            block_y = defend_goal_y + sign * 35.0

            # Narrow the angle by shading toward the opponent's lateral position

            block_x = max(36.0, min(64.0, 50.0 + (opponent["x"] - 50.0) * 0.4))

            # Move toward mid-block position

            preferred = direction_toward(block_x - me["x"], block_y - me["y"], dead_zone=1.0)

            # Hold the mid-block line

            return {"move": _safe_move(observation, preferred)}



        # Maldini Axiom 4: Disciplined Jockeying on the Bisector

        # Maintain a 9.5 unit cushion along the line between opponent and our goal

        raw_jockey_x = opponent["x"] + ux_to_goal * 9.5

        # Clamp jockey horizontal position to strictly protect the 35-to-65 goal mouth

        jockey_x = max(35.0, min(65.0, raw_jockey_x))

        # Keep our body strictly goal-side of the attacker

        jockey_y = opponent["y"] + uy_to_goal * 9.5

        # Ensure our jockey position never drops behind our goal line

        if sign > 0:

            # When defending bottom goal line, stay at least 4.5 units in front

            jockey_y = max(defend_goal_y + 4.5, jockey_y)

        # Alternative branch condition: else:

        else:

            # When defending top goal line, stay at least 4.5 units in front

            jockey_y = min(defend_goal_y - 4.5, jockey_y)

        # Steer toward our jockey containment point to block all shooting cones

        preferred = direction_toward(jockey_x - me["x"], jockey_y - me["y"], dead_zone=1.0)

        # Execute disciplined jockeying step

        return {"move": _safe_move(observation, preferred)}



    # Franz Beckenbauer / Lothar Matthäus Persona (Loose Ball Sweeping and Recovery)

    target_x, target_y = ball["x"], ball["y"]

    # If the ball is moving, anticipate where it will arrive in the next simulation tick

    if ball["status"] == "moving":

        # Add horizontal velocity to predict future ball position

        target_x += vx

        # Add vertical velocity to predict future ball position

        target_y += vy



    # Calculate straight-line distance from our bot to the loose ball

    dist_me_to_ball = math.hypot(target_x - me["x"], target_y - me["y"])

    # Calculate straight-line distance from opponent to the loose ball

    dist_opp_to_ball = math.hypot(target_x - opponent["x"], target_y - opponent["y"])



    # Beckenbauer Sweeper Axiom: If opponent has a clear head start to the loose ball, do NOT chase behind them!

    if dist_opp_to_ball < dist_me_to_ball - 3.5:

        # Distance from loose ball to our defending goal line

        ball_dist_to_our_goal = abs(target_y - defend_goal_y)

        # If the ball is in our defensive half (within 70 units of our goal)

        if ball_dist_to_our_goal <= 70.0:

            # Set up a defensive block in front of the goal along the shooting line

            guard_y = defend_goal_y + sign * max(5.0, min(25.0, ball_dist_to_our_goal * 0.4))

            # Protect the 36 to 64 central goal mouth

            guard_x = max(36.0, min(64.0, 50.0 + (target_x - 50.0) * 0.35))

            # Move toward defensive guarding coordinate

            preferred = direction_toward(guard_x - me["x"], guard_y - me["y"], dead_zone=1.5)

            # Execute disciplined defensive retreat

            return {"move": _safe_move(observation, preferred)}

        # Alternative branch condition: else:

        else:

            # Ball is in opponent's half; hold the midfield defensive line (38 units from our goal)

            guard_y = defend_goal_y + sign * 38.0

            # Track the ball horizontally while staying centered

            guard_x = max(36.0, min(64.0, 50.0 + (target_x - 50.0) * 0.35))

            # Move toward midfield shape

            preferred = direction_toward(guard_x - me["x"], guard_y - me["y"], dead_zone=1.5)

            # Maintain team shape

            return {"move": _safe_move(observation, preferred)}



    # Otherwise sprint at top speed directly toward the anticipated loose ball location

    preferred = direction_toward(target_x - me["x"], target_y - me["y"], dead_zone=0.5)

    # Execute recovery sprint

    return {"move": _safe_move(observation, preferred)}





# The Policy Class: this is the complete Policy object that loads saved Q-tables and makes decisions

class Policy:

    """Standalone inference policy for the sparse RL models made by train_bot.py."""



    # Set up the brain with its memory table, visit counts, and safety settings

    def __init__(

        # Execute operational logic: self,

        self,

        # Execute operational logic: q_table: dict[str, list[float]] | None = None,

        q_table: dict[str, list[float]] | None = None,

        # Execute operational logic: visits: dict[str, int] | None = None,

        visits: dict[str, int] | None = None,

        # Execute operational logic: seed: int = 0,

        seed: int = 0,

        # Execute operational logic: evaluation_epsilon: float = 0.03,

        evaluation_epsilon: float = 0.03,

        # Execute operational logic: safety_margin: float = 0.6,

        safety_margin: float = 0.6,

        # Execute operational logic: kick_power: int = 3,

        kick_power: int = 3,

    # Execute operational logic: ) -> None:

    ) -> None:

        # The Q-table memory: maps situation fingerprints to a list of scores for each action

        self.q_table = q_table or {}

        # Tracks how many times our bot has encountered each situation during training

        self.visits = visits or {}

        # The random seed number for repeatable results

        self.model_seed = seed

        # Small exploration rate during evaluation (3% chance of testing a random move)

        self.evaluation_epsilon = evaluation_epsilon

        # Safety buffer: only use learned move if it beats the safe fallback move by at least 0.6 points

        self.safety_margin = safety_margin

        # Default kick power to use when shooting

        self.kick_power = kick_power

        # Random number generator object

        self.random = random.Random(seed)

        # Flag to remember whether we have seeded this match yet

        self.match_seeded = False



    # Factory method: loads a trained JSON model file from your computer's hard drive

    @classmethod

    # Function declaration: def load(cls, path: Path) -> "Policy":

    def load(cls, path: Path) -> "Policy":

        # Read the text of the JSON file and parse it into a Python dictionary

        raw = json.loads(path.read_text(encoding="utf-8"))

        # Check that the file format matches format 3 and has all 33 possible actions

        if raw.get("format") == 3 and raw.get("action_count") == ACTION_COUNT:

            # Execute operational logic: q_table: dict[str, list[float]] = {}

            q_table: dict[str, list[float]] = {}

            # Reconstruct the full list of 33 action scores for each saved state

            for key, sparse in raw.get("q_table", {}).items():

                # Execute operational logic: values = [0.0] * ACTION_COUNT

                values = [0.0] * ACTION_COUNT

                # Iteration loop: for index, value in sparse.items():

                for index, value in sparse.items():

                    # Execute operational logic: values[int(index)] = float(value)

                    values[int(index)] = float(value)

                # Execute operational logic: q_table[key] = values

                q_table[key] = values

            # Return a fully loaded Policy brain with all learned memories restored

            return cls(

                # Execute operational logic: q_table=q_table,

                q_table=q_table,

                # Execute operational logic: visits={key: int(value) for key, value in raw.get("visits", {}).items()},

                visits={key: int(value) for key, value in raw.get("visits", {}).items()},

                # Execute operational logic: seed=int(raw.get("seed", 0)),

                seed=int(raw.get("seed", 0)),

                # Execute operational logic: evaluation_epsilon=float(raw.get("evaluation_epsilon", 0.03)),

                evaluation_epsilon=float(raw.get("evaluation_epsilon", 0.03)),

                # Execute operational logic: safety_margin=float(raw.get("safety_margin", 0.6)),

                safety_margin=float(raw.get("safety_margin", 0.6)),

            # Execute operational logic: )

            )

        # If the file is just a simple fallback template, return a basic policy

        return cls(kick_power=int(raw.get("kick_power", 3)))



    # Generates a unique text "fingerprint" string representing the current situation on the pitch

    @staticmethod

    # Function declaration: def state_key(observation: dict[str, Any]) -> str:

    def state_key(observation: dict[str, Any]) -> str:

        # Extract our bot's unique player ID ('player_1' or 'player_2')

        player_id = observation["player_id"]

        # Extract the opponent bot's unique player ID

        opponent_id = observation["opponent_id"]

        # Access the complete match state containing all pitch entities

        state = observation["state"]

        # Access the stadium dimensions dictionary

        field = state["field"]

        # Look up our own player's current coordinate and body details

        me = state["players"][player_id]

        # Look up the opponent's current coordinate and body details

        opponent = state["players"][opponent_id]

        # Look up the ball's current location, speed, and possession status

        ball = state["ball"]

        # Fetch the numerical width and height of the playing field

        width, height = float(field["width"]), float(field["height"])

        # Set directional multiplier (+1 when attacking UP, -1 when attacking DOWN)

        sign = 1.0 if observation["attack_direction"] == "UP" else -1.0

        # Normalize our Y coordinate relative to the goal we are attacking

        attack_y = me["y"] if sign > 0 else height - me["y"]

        # Distance and direction to the ball from our player

        ball_dx, ball_dy = ball["x"] - me["x"], sign * (ball["y"] - me["y"])

        # Distance and direction to the opponent from our player

        opponent_dx = opponent["x"] - me["x"]

        # Relative vertical distance to the opponent along our attacking axis

        opponent_dy = sign * (opponent["y"] - me["y"])

        # Access the ball's current speed and movement velocity

        velocity = ball.get("velocity", {})

        # Find which obstacle is closest to our player and what direction it is in

        nearest = (999.0, 8)

        # Scan through each obstacle block on the soccer field

        for obstacle in state.get("obstacles", []):

            # Calculate distance from player to center of the obstacle

            dx = obstacle["x"] + obstacle["width"] / 2 - me["x"]

            # Calculate relative vertical distance to the center of the obstacle

            dy = sign * (obstacle["y"] + obstacle["height"] / 2 - me["y"])

            # Calculate straight-line Euclidean distance to obstacle

            distance = math.hypot(dx, dy)

            # If this obstacle is closer than any previously checked, remember it

            if distance < nearest[0]:

                # Execute operational logic: nearest = (distance, _sector(dx, dy))

                nearest = (distance, _sector(dx, dy))

        # Who has the ball: 'S' for Self, 'O' for Opponent, 'F' for Free (loose ball)

        possession = "S" if ball["possession"] == player_id else "O" if ball["possession"] == opponent_id else "F"

        # Combine all key observations into simple discrete numbers (buckets and sectors)

        values = (

            min(4, int(me["x"] / width * 5)),                                           # Our X position (5 zones)

            min(6, int(attack_y / height * 7)),                                         # Our Y position (7 zones)

            _sector(ball_dx, ball_dy),                                                  # Direction to the ball (0-7)

            _bucket(math.hypot(ball_dx, ball_dy), (7, 16, 32, 60)),                     # Distance to the ball (5 buckets)

            _sector(opponent_dx, opponent_dy),                                          # Direction to the opponent

            _bucket(math.hypot(opponent_dx, opponent_dy), (8, 18, 38, 70)),             # Distance to opponent

            possession,                                                                 # Who has the ball ('S', 'O', 'F')

            ball["status"][0].upper(),                                                  # Ball status ('M'oving, 'S'tationary, etc.)

            _sector(float(velocity.get("x", 0.0)), sign * float(velocity.get("y", 0.0))), # Ball flight direction

            _bucket(float(ball.get("remaining_kick_distance", 0.0)), (1, 25, 60)),      # How much kick distance remains

            _bucket(int(ball.get("possession_steps", 0)), (1, 3, 6)),                   # How long we held the ball

            nearest[1] if nearest[0] < 24 else 8,                                       # Direction to nearest obstacle

            _bucket(nearest[0], (8, 16, 24)),                                           # Distance to nearest obstacle

        # Execute operational logic: )

        )

        # Join all the numbers together with pipe symbols (e.g. "2|4|3|1|0|2|S|M|1|0|1|8|3")

        return "|".join(map(str, values))



    # Converts an action index number (0 to 32) into an actual movement/kick command dictionary

    @staticmethod

    # Function declaration: def action_from_index(index: int) -> dict[str, Any]:

    def action_from_index(index: int) -> dict[str, Any]:

        # Indices 0 to 8 represent pure movements (no kick)

        if index < len(MOVES):

            # Return calculated outcome: return {"move": MOVES[index]}

            return {"move": MOVES[index]}

        # Indices 9 to 32 represent kick combinations (direction + power level)

        kick_index = index - len(MOVES)

        # Execute operational logic: direction = KICK_DIRECTIONS[kick_index // 3]

        direction = KICK_DIRECTIONS[kick_index // 3]

        # Return calculated outcome: return {"move": direction, "kick": {"direction": direction, "power": kick_index % 3 + 1}}

        return {"move": direction, "kick": {"direction": direction, "power": kick_index % 3 + 1}}



    # Converts an action dictionary back into its corresponding index number (0 to 32)

    @staticmethod

    # Function declaration: def index_from_action(action: dict[str, Any]) -> int:

    def index_from_action(action: dict[str, Any]) -> int:

        # Execute operational logic: kick = action.get("kick")

        kick = action.get("kick")

        # Decision branch condition: if isinstance(kick, dict) and kick.get("direction") in KICK_DIRECTIONS:

        if isinstance(kick, dict) and kick.get("direction") in KICK_DIRECTIONS:

            # Execute operational logic: power = max(1, min(3, int(kick.get("power", 1))))

            power = max(1, min(3, int(kick.get("power", 1))))

            # Return calculated outcome: return len(MOVES) + KICK_DIRECTIONS.index(kick["direction"]) * 3 + power - 1

            return len(MOVES) + KICK_DIRECTIONS.index(kick["direction"]) * 3 + power - 1

        # Return calculated outcome: return MOVES.index(action.get("move", "STAY"))

        return MOVES.index(action.get("move", "STAY"))



    # Finds all action indices that are legally possible and safe right now (won't run into walls)

    @staticmethod

    # Function declaration: def valid_indices(observation: dict[str, Any]) -> list[int]:

    def valid_indices(observation: dict[str, Any]) -> list[int]:

        # Check which of the 8 moving directions are safe to step into

        moves = [index for index in range(1, len(MOVES)) if _move_is_safe(observation, MOVES[index])]

        # Execute operational logic: ball = observation["state"]["ball"]

        ball = observation["state"]["ball"]

        # If we do NOT have the ball, we are not allowed to kick! Only return movement choices

        if ball["possession"] != observation["player_id"]:

            # Return calculated outcome: return moves or [0]

            return moves or [0]

        # If we possess the ball, look at forward directions toward the opponent's goal

        attack = observation["attack_direction"]

        # Execute operational logic: forward = [attack, f"{attack}_LEFT", f"{attack}_RIGHT"]

        forward = [attack, f"{attack}_LEFT", f"{attack}_RIGHT"]

        # In the first 2 ticks of possession, focus on controlling and dribbling forward

        if int(ball.get("possession_steps", 0)) < 2:

            # Execute operational logic: controlled = [MOVES.index(move) for move in forward if _move_is_safe(observation, move)]

            controlled = [MOVES.index(move) for move in forward if _move_is_safe(observation, move)]

            # Return calculated outcome: return controlled or moves or [0]

            return controlled or moves or [0]

        # After 2 ticks of control, all forward kicks at all 3 powers are also legal options

        kicks = [

            # Execute operational logic: len(MOVES) + KICK_DIRECTIONS.index(direction) * 3 + power

            len(MOVES) + KICK_DIRECTIONS.index(direction) * 3 + power

            # Iteration loop: for direction in forward

            for direction in forward

            # Iteration loop: for power in range(3)

            for power in range(3)

        # Execute operational logic: ]

        ]

        # Return calculated outcome: return moves + kicks

        return moves + kicks



    # The master decision function: this is called every single tick to choose our bot's next move

    def choose_action(self, observation: dict[str, Any]) -> dict[str, Any]:

        # Initialize random seed on the very first tick of the match

        if not self.match_seeded:

            # Execute operational logic: state_seed = int(observation["state"].get("seed", 0))

            state_seed = int(observation["state"].get("seed", 0))

            # Execute operational logic: side_seed = 17 if observation["player_id"] == "player_1" else 31

            side_seed = 17 if observation["player_id"] == "player_1" else 31

            # Execute operational logic: self.random.seed(self.model_seed ^ (state_seed * 1_000_003) ^ side_seed)

            self.random.seed(self.model_seed ^ (state_seed * 1_000_003) ^ side_seed)

            # Execute operational logic: self.match_seeded = True

            self.match_seeded = True



        # Step 1: Calculate the safe rule-based "tactical fallback" action

        fallback_action = tactical_action(observation, self.kick_power)

        # Step 2: Get all actions that are safe to execute right now without crashing

        valid = self.valid_indices(observation)

        # Step 3: Look up our memory scores for this specific situation in the Q-table

        values = self.q_table.get(self.state_key(observation))



        # Check: If this situation is completely new, or visited less than 2 times, use the safe rule!

        if values is None or self.visits.get(self.state_key(observation), 0) < 2:

            # Return calculated outcome: return fallback_action

            return fallback_action

        # Check: With 3% probability, try a random safe move to keep play unpredictable

        if self.random.random() < self.evaluation_epsilon:

            # Return calculated outcome: return self.action_from_index(self.random.choice(valid))

            return self.action_from_index(self.random.choice(valid))

        # Step 4: Find the highest action score in our learned Q-table for this situation

        best = max(values[index] for index in valid)

        # Check: Convert our safe fallback move to an index number

        fallback = self.index_from_action(fallback_action)

        # Safety Check: If the learned move is only slightly better than the safe fallback move, prefer safety!

        if fallback in valid and best - values[fallback] < self.safety_margin:

            # Return calculated outcome: return fallback_action

            return fallback_action

        # Step 5: If the learned move is clearly superior, execute the highest scoring action!

        choices = [index for index in valid if abs(values[index] - best) < 1e-9]

        # Return calculated outcome: return self.action_from_index(self.random.choice(choices))

        return self.action_from_index(self.random.choice(choices))

