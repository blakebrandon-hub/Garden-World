"""
Garden World Day Advancement System with Health & Watering
Handles automatic plant growth, health degradation, and plant death
"""

import random
from datetime import datetime
from storage import (
    get_plants, update_plant_stage, get_game_state,
    add_message, update_plant_health, remove_plant,
    PLANT_CONFIGS, update_game_state
)


def advance_world_day():
    """
    Advance the world by one day (24-hour ship cycle).
    1. Increment day counter
    2. Check each plant's watering needs
    3. Degrade health if not watered
    4. Kill plants below health threshold
    5. Progress healthy plants through growth stages
    6. Log the day advancement
    """
    print(f"\n🌅 === ADVANCING WORLD DAY === {datetime.now().isoformat()}")

    state = get_game_state()
    current_day = state.get('current_day', 0)
    new_day = current_day + 1

    update_game_state(current_day=new_day)
    print(f"📅 Ship Day {current_day} → Day {new_day}")

    plants = get_plants()

    if not plants:
        print("🌱 No plants in the garden yet")
        add_message('narrator', 'Narrator', f"Ship day {new_day} begins. The garden lies empty, waiting.")
        return {
            'day': new_day,
            'plants_advanced': 0,
            'plants_suffering': 0,
            'plants_died': 0,
            'status': 'success'
        }

    plants_advanced = 0
    plants_suffering = 0
    plants_died = 0

    growth_progression = {
        'Seed': 'Sprout',
        'Sprout': 'Leafing',
        'Leafing': 'Flowering',
        'Flowering': 'Fruit',
        'Fruit': 'Harvest'
    }

    deceased_plants = []

    # We need to mutate the in-memory list, so work directly
    import storage as _store

    for plant in list(plants):  # list() so we can safely remove during iteration
        plant_id = plant['id']
        plant_name = plant['name']
        plant_type = plant['plant_type']
        current_stage = plant['stage']
        current_health = plant.get('health', 100)
        days_since_watered = plant.get('days_since_watered', 0)

        config = PLANT_CONFIGS.get(plant_type, {'water_frequency': 2})
        water_frequency = config['water_frequency']

        # Increment days_since_watered directly on the object
        p_obj = _store._find_plant(plant_id)
        if p_obj:
            p_obj['days_since_watered'] = days_since_watered + 1
        new_days_since_watered = days_since_watered + 1

        needs_water = new_days_since_watered > water_frequency

        if needs_water:
            days_overdue = new_days_since_watered - water_frequency
            if days_overdue == 1:
                health_loss = -random.randint(8, 12)
            elif days_overdue == 2:
                health_loss = -random.randint(13, 18)
            elif days_overdue == 3:
                health_loss = -random.randint(18, 22)
            else:
                health_loss = -random.randint(23, 27)

            new_health = max(0, current_health + health_loss)
            update_plant_health(plant_id, health_loss)

            print(f"💧 {plant_name}: Thirsty! Health {current_health}% → {new_health}%")
            plants_suffering += 1

            if new_health <= 0:
                print(f"🥀 {plant_name}: Died from dehydration")
                deceased_plants.append({'name': plant_name, 'type': plant_type, 'cause': 'dehydration'})
                remove_plant(plant_id)
                plants_died += 1
                continue

            current_health = new_health
        else:
            print(f"💚 {plant_name}: Well-watered ({new_days_since_watered}/{water_frequency} days)")

        if current_health >= 50:
            if current_stage in growth_progression:
                next_stage = growth_progression[current_stage]
                update_plant_stage(plant_id, next_stage)
                print(f"🌱 {plant_name}: {current_stage} → {next_stage}")
                plants_advanced += 1
            else:
                print(f"🌾 {plant_name}: Already at {current_stage}")
        else:
            print(f"⚠️  {plant_name}: Too weak to grow (health: {current_health}%)")

    # Build narrator message
    parts = [f"Ship day {new_day} begins. The grow lights brighten."]
    if plants_advanced > 0:
        parts.append(f"{plants_advanced} plant(s) have grown.")
    if plants_suffering > 0:
        parts.append(f"{plants_suffering} plant(s) are suffering from lack of water.")
    for deceased in deceased_plants:
        parts.append(f"{deceased['name']} has withered completely.")
    if plants_suffering == 0 and plants_died == 0 and plants_advanced > 0:
        parts.append("The garden thrives.")

    add_message('narrator', 'Narrator', " ".join(parts))

    print(f"\n✅ Day advancement complete: {plants_advanced} grew, {plants_suffering} suffering, {plants_died} died\n")

    return {
        'day': new_day,
        'plants_advanced': plants_advanced,
        'plants_suffering': plants_suffering,
        'plants_died': plants_died,
        'deceased_plants': deceased_plants,
        'status': 'success'
    }


def get_current_day() -> int:
    state = get_game_state()
    return state.get('current_day', 0)
