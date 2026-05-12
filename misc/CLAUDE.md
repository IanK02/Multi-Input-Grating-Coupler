# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research codebase for **inverse design of photonic integrated circuits** using [Tidy3D](https://docs.flexcompute.com/projects/tidy3d/), an FDTD electromagnetic simulation platform. The primary application is designing **grating couplers** — devices that couple light between optical fibers and silicon photonic waveguides.

All simulations are run on Flexcompute's cloud (`tidy3d.simulation.cloud`) via `tidy3d.web`. Each simulation run consumes **FlexCredits**; use `web.estimate_cost(job.task_id)` before running.

## Running Code

All work is done in **Jupyter notebooks** (`.ipynb`). There are no build steps, test suites, or CLI scripts. The only standalone Python file is `test.py` (a one-liner for API connectivity testing).

```bash
# Check Tidy3D API connectivity
python test.py

# Launch Jupyter to work with notebooks
jupyter notebook
```

## Key Dependencies

- `tidy3d` — FDTD simulation engine + cloud runner
- `autograd` / `autograd.numpy` — automatic differentiation for adjoint optimization
- `optax` — gradient-based optimizer (Adam)
- `numpy`, `scipy`, `matplotlib` — standard scientific computing
- `pickle` — checkpointing optimization history

## Architecture & Code Structure

### Inverse Design Loop (adjoint method)

The core optimization pattern used in `grating_couplers/Autograd6GC_gaussian.ipynb` and `grating_couplers/farfield_obj_function/Autograd6GratingCoupler_farfield.ipynb`:

1. **Design parameters** (`params`, shape `[nx, ny]`) are values in `[0, 1]` representing material density
2. **Pre-processing pipeline**: `interface_buffer` → `filter_project` (x2, conic density filter) → `rescale` to permittivity range `[eps_min, eps_max]`
3. **Simulation**: `make_adjoint_sim()` creates a `td.Simulation` with a `td.CustomMedium` for the design region
4. **Objective function**: Either waveguide mode overlap (power coupling) or far-field Gaussian beam overlap at 100 µm projection distance
5. **Gradient**: `value_and_grad(obj)` from `autograd` computes J and dJ/dp in one forward+adjoint pass
6. **Optimizer**: Adam via `optax`, with beta (binarization sharpness) annealed from `beta_min=1` to `beta_max=30`
7. **Checkpointing**: History saved to `.pkl` files in `misc/`; optimization resumes automatically from checkpoint

### Objective Functions

Two FOM approaches are present:
- **Waveguide mode overlap**: `ModeMonitor` captures power coupled into waveguide mode (earlier notebooks)
- **Far-field Gaussian overlap**: `FieldProjectionCartesianMonitor` projects near-field to 100 µm, then computes overlap integral with analytic Gaussian target (newest approach, in `farfield_obj_function/`)

### Simulation Structure (grating coupler)

```
Structures: waveguide (Si3N4) | SiO2 BOX layer | Si3N4 substrate | design_region (CustomMedium)
Source:     ModeSource at waveguide input, firing toward grating (+x direction)
Monitor:    FieldMonitor just above design region (near-field, for projection)
Symmetry:   (0, -1, 0) — mirror symmetry in y exploited for 2x speedup
```

### Material System

- Si3N4 waveguide/grating: n = 2.03 (eps ≈ 4.12), target wavelength λ = 0.729 µm
- SiO2 BOX: n = 1.44
- Air cladding: n = 1.0

### Key Files

| Path | Purpose |
|------|---------|
| `grating_couplers/Autograd6GC_gaussian.ipynb` | Main active optimization (far-field FOM, current) |
| `grating_couplers/farfield_obj_function/Autograd6GratingCoupler_farfield.ipynb` | Earlier far-field FOM notebook |
| `grating_couplers/farfield_obj_function/analytic_solutions.py` | `analytic_gaussian_beam()` utility for target field generation |
| `gaussian_propogation.ipynb` | Standalone Gaussian beam propagation tests |
| `grating_couplers/misc/` | Optimization history `.pkl` checkpoints |
| `grating_couplers/data/` | Saved simulation `.hdf5` results |

### Simulation Data Persistence

- Simulation results saved as `.hdf5` via `job.run(path="data/...")`
- Loaded back via `td.SimulationData.from_file()` or automatically by `job.run()`
- Optimization history (params, gradients, objective values) saved as pickle in `misc/`

## Important Tidy3D Patterns

```python
# Run a simulation (cloud, costs FlexCredits)
job = web.Job(simulation=sim, task_name="my_task")
web.estimate_cost(job.task_id)      # check cost first
sim_data = job.run(path="data/sim.hdf5")

# Quick run without Job wrapper
sim_data = web.run(sim, task_name="my_task", verbose=True)

# Load previously saved simulation data
sim_data = td.SimulationData.from_file("data/sim.hdf5")

# Far-field projection (computed post-simulation, no cloud cost)
projector = td.FieldProjector.from_near_field_monitors(sim_data, near_monitors=[...], normal_dirs=["+"])
proj_fields = projector.project_fields(monitor_far)
```

## Autograd Compatibility

When writing the objective function, use `autograd.numpy as anp` instead of `numpy` for all operations that need to be differentiated. Standard `numpy` can be used for non-differentiable parts (monitor setup, plotting). The `tidy3d.plugins.autograd` module provides `make_filter_and_project`, `rescale`, and `make_erosion_dilation_penalty` that are autograd-compatible.

## Iteration Notes & Design Log (`notes.md`)

A file `notes.md` at the project root tracks lessons learned from each completed inverse design iteration. An **iteration** is defined as: the full inverse design procedure has finished (optimization converged or was stopped) **and** far-field projections of that device have been calculated.

### After each completed iteration

When an iteration is complete (optimization done + far-field projections computed), **ask the user**:

> "The iteration is complete. What did you observe or learn from this device? What would you like to improve, and how do you think it could be done?"

Then record their response in `notes.md` under a new numbered entry using this format:

```markdown
## Iteration N — <short descriptive title>
**Date:** YYYY-MM-DD
**Notebook:** <notebook filename>
**Result:** <key metric, e.g. coupling efficiency, J value, far-field peak>

### Findings
<user's observations about what this device did>

### What to Improve
<user's stated goals for the next iteration>

### Proposed Approach
<user's ideas on how to achieve those improvements>

### Additional Notes
<any other context, parameter settings, or lessons learned>
```

If `notes.md` does not yet exist, create it with a header before the first entry:

```markdown
# Inverse Design Iteration Log

This file records findings, observations, and lessons learned from each completed
inverse design iteration on the grating coupler project.

---
```

### When working on a new device

**Before starting** any new inverse design run or making changes to the optimization setup, **read `notes.md`** and explicitly reference relevant past findings. For example:

- If a prior iteration noted that beta annealing improved binarization, apply or consider that here.
- If a prior iteration noted poor far-field beam shape, check whether the proposed fix was implemented.
- Proactively remind the user of relevant lessons from `notes.md` when suggesting parameter changes or new approaches.

Reference `notes.md` often during design discussions — treat it as the primary source of accumulated experimental knowledge for this project.
