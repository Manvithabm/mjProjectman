import traci
from traci.exceptions import FatalTraCIError

SUMO_CONFIG = "simulation.sumocfg"
VAC_TRIPINFO_OUTPUT = "tripinfo_vac.xml"
VAC_EMISSIONS_OUTPUT = "emissions_vac.xml"
MIN_PHASE_HOLD_STEPS = 8
SUMO_BINARY = "sumo"

traci.start(
    [
        SUMO_BINARY,
        "-c",
        SUMO_CONFIG,
        "--tripinfo-output",
        VAC_TRIPINFO_OUTPUT,
        "--emission-output",
        VAC_EMISSIONS_OUTPUT,
    ]
)

def _lane_counts_for_tls(tls_id):
    lane_counts = {}
    for lane in traci.trafficlight.getControlledLanes(tls_id):
        if lane not in lane_counts:
            lane_counts[lane] = traci.lane.getLastStepVehicleNumber(lane)
    return lane_counts


def _phase_pressure(tls_id, phase_state, controlled_links, lane_counts):
    pressure = 0
    for signal_index, signal_state in enumerate(phase_state):
        if signal_state not in ("g", "G"):
            continue
        if signal_index >= len(controlled_links):
            continue
        for link in controlled_links[signal_index]:
            if not link:
                continue
            in_lane = link[0]
            pressure += lane_counts.get(in_lane, 0)
    return pressure


def _choose_best_phase(tls_id, lane_counts):
    logics = traci.trafficlight.getAllProgramLogics(tls_id)
    if not logics:
        return traci.trafficlight.getPhase(tls_id), 0

    phases = logics[0].phases
    controlled_links = traci.trafficlight.getControlledLinks(tls_id)

    current_phase = traci.trafficlight.getPhase(tls_id)
    best_phase = current_phase
    best_pressure = -1

    for phase_index, phase in enumerate(phases):
        phase_state = phase.state
        # Ignore all-red / all-yellow phases for selection.
        if "g" not in phase_state and "G" not in phase_state:
            continue

        pressure = _phase_pressure(tls_id, phase_state, controlled_links, lane_counts)
        if pressure > best_pressure:
            best_pressure = pressure
            best_phase = phase_index

    return best_phase, best_pressure


step = 0
warned_no_tls = False
last_switch_step = {}

while step < 1000:
    try:
        traci.simulationStep()
    except FatalTraCIError:
        print("SUMO closed the TraCI connection (simulation likely finished).", flush=True)
        break

    tls_ids = traci.trafficlight.getIDList()
    if not tls_ids and not warned_no_tls:
        print(
            "No traffic lights found in network.net.xml. "
            "Generate the network with TLS (e.g. --tls.guess) to use VAC control.",
            flush=True,
        )
        warned_no_tls = True

    for tls in tls_ids:
        lane_counts = _lane_counts_for_tls(tls)
        vehicle_count = sum(lane_counts.values())
        print(f"Signal: {tls}, Vehicles: {vehicle_count}", flush=True)

        best_phase, best_pressure = _choose_best_phase(tls, lane_counts)
        current_phase = traci.trafficlight.getPhase(tls)

        if tls not in last_switch_step:
            last_switch_step[tls] = step

        steps_since_switch = step - last_switch_step[tls]
        if best_phase != current_phase and steps_since_switch >= MIN_PHASE_HOLD_STEPS:
            traci.trafficlight.setPhase(tls, best_phase)
            last_switch_step[tls] = step
            print(
                f"  -> switched {tls} to phase {best_phase} (pressure={best_pressure})",
                flush=True,
            )

    if traci.simulation.getMinExpectedNumber() <= 0:
        print("No more vehicles expected in simulation. Stopping control loop.", flush=True)
        break

    step += 1

traci.close()