# Car Racing Championship Simulation  
**Design Spec for a Coding LLM**

---

## 1. Game Overview

Create a **single-player championship-style car racing management game** (no real-time driving).

- The player competes against **4 AI-controlled drivers** in a **5-race championship**.
- Format is similar to a **Formula 1** race weekend.
- There is **no manual driving**: all sessions are **simulated** based on:
  - Car setup
  - Driver characteristics
  - Track characteristics
  - Weather and time of day

The player:

1. Tunes their car.
2. Chooses 2 strengths for their driver.
3. Runs free practice laps (with between-lap tuning).
4. Qualifies.
5. Simulates the race.

---

## 2. Core Structure

### 2.1 Championship

- **Number of races:** 5  
- **Number of drivers:** 5
  - 1 human player
  - 4 AI bots
- **Each race:** different track with unique characteristics.
- **Points system:** define a simple points table, e.g.  
  1st–5th = 10, 8, 6, 4, 2 (or any reasonable table).

### 2.2 Race Weekend Format

Each race weekend consists of:

1. **Car Tuning Phase** (player only; pre-practice baseline)
2. **Driver Selection / Trait Adjustment** (only at start of championship)
3. **Free Practice Session**
   - 5 laps per driver
   - Player can **adjust car setup before each practice lap**
4. **Qualifying**
   - 1 out-lap (ignored) + 1 hot lap per driver
   - Results determine starting grid
5. **Race**
   - 10 laps per driver
   - Results determine race points and driver progression

For all 5 races, repeat steps:

- 1: Car tuning
- 3: Free practice
- 4: Qualifying
- 5: Race

Driver trait selection (step 2) happens **once at the start**, but traits can evolve.

---

## 3. Entities & Data Model

Design data structures (classes/structs) for **Track**, **Weather**, **TimeOfDay**, **Car**, and **Driver**.

### 3.1 Track

Each of the 5 tracks has:

- `name: string`
- `complexityProfile: number` (0–100)  
  - Represents combined corner complexity: long sweepers, hairpins, chicanes, S-bends.
- `aeroDemand: number` (0–100)  
  - Higher value rewards strong downforce and punishes draggy setups.
- `surfaceGrip: number` (0–100)  
  - Overall grip level of the tarmac.
- `surfaceBumpiness: number` (0–100)  
  - Bumpy surfaces increase importance of mechanical grip and stability.
- `elevationChange: number` (0–100)  
  - Influence of up/downhill and undulations on car balance.
- `baseLapTime: number`  
  - Reference lap time in seconds for a “neutral” car and driver in ideal conditions.

You may optionally define **default weather tendencies** per track, but actual weather is per session.

### 3.2 Weather

Define weather as:

- `conditions: enum | list<enum>`  
  - Possible values:
    - `HOT`
    - `COLD`
    - `RAINY`
    - `WINDY`
  - Allow combination, e.g. `["RAINY", "WINDY"]`.
- `gripModifier: number`  
  - Adjusts effective track grip (RAINY lowers it).
- `aeroStabilityModifier: number`  
  - Wind increases instability for aero-sensitive cars.
- `enginePerformanceModifier: number`  
  - Very hot/cold affects power unit performance.
- `visibilityModifier: number`  
  - Impacts driver mistakes and consistency.

Each session (Practice, Qualifying, Race) gets its own **actual weather**, possibly derived from a forecast.

### 3.3 Time of Day

For the **race session**:

- `timeOfDay: enum`
  - `MORNING | AFTERNOON | EVENING | NIGHT`

Optional modifiers:

- `trackTempModifier` (affects grip and tyre performance).
- `driverFocusModifier` (e.g. night can change error rates).

### 3.4 Car

Each car has tune-able characteristics:

- `aeroEfficiency: number` (0–100)  
  - Downforce vs drag balance. Higher downforce improves cornering but may increase drag.
- `mechanicalGrip: number` (0–100)  
  - Suspension + tyres effectiveness.
- `powerUnit: number` (0–100)  
  - Power output and delivery characteristics.
- `cornerBalance: number` (0–100)  
  - Stability across corner phases (entry, mid-corner, exit).
- `aeroSensitivity: number` (0–100)  
  - How narrow the optimal aero window is. High values mean more sensitivity to non-ideal conditions.

**Tuning Rules:**

- Start each championship (or race) from a default mid-range base (e.g., 50 for each stat).
- **Car Tuning Phase (pre-practice):**
  - Player creates an initial baseline setup for the race track.
- During practice, the player can **refine** this setup between laps (see Free Practice section).
- To prevent extreme changes:
  - You may limit the total adjustment per attribute per race or per lap.
- AI cars:
  - Generate setups using simple heuristics:
    - Increase `aeroEfficiency` (toward downforce) on high `aeroDemand` tracks.
    - Increase `mechanicalGrip` on low-grip or bumpy tracks, etc.

Once the player confirms their setup after practice, it is **locked** for qualifying and race.

### 3.5 Driver

Each driver has 5 characteristics (0–100):

1. `carControl`  
   - Car control under instability.
2. `consistency`  
   - Pace stability across laps and conditions.
3. `racecraft`  
   - Overtaking, defending, spatial awareness.
4. `adaptability`  
   - Ability to handle evolving car balance and changing track/weather.
5. `mentalResilience`  
   - Performance under pressure and in critical race moments.

#### Player Driver Choice

- At **championship start**:
  - Show all 5 driver attributes.
  - Player chooses **2 attributes** to specialize in.
    - Add a defined boost (e.g. +20 points) to those 2 attributes.
  - The remaining attributes are set to base values (e.g. around 50).
- These 2 chosen attributes become the driver’s **focus strengths** and cannot be reassigned mid-championship (though they can still evolve through progression).

#### Driver Progression

After each race:

- For each driver (player + AI):
  - Compare **qualifying position** to **finishing position**.
  - If driver finishes **better** than they started:
    - Increase relevant stats slightly (e.g. +1 to +3 each):
      - Gaining positions → improve `racecraft` and `mentalResilience`.
      - Maintaining a strong position under pressure → improve `consistency` and `mentalResilience`.
      - Big gains in tricky weather → improve `adaptability` and `carControl`.
  - If driver finishes **worse**:
    - Optionally apply small negative adjustments (e.g. −1 to −2) or choose only positive progression if preferred.

---

## 4. Simulation Model

The game simulates:

- Practice lap times
- Qualifying lap times
- Race lap times and position changes

Lap times are based on:

- Track parameters
- Car setup
- Driver stats
- Weather & time of day
- Random variation

Use a deterministic formula plus random noise.

### 4.1 Base Lap Time Formula (Conceptual)

For each lap:

```pseudo
base = track.baseLapTime
carFactor = fCar(track, car, weather)
driverFactor = fDriver(driver, weather, sessionType, pressureLevel)
randomFactor = smallRandomNoise()

lapTime = base - carFactor - driverFactor + randomFactor
