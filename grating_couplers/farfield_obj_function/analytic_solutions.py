def analytic_gaussian_beam(proj_monitor, r_proj, waist_radius):
    """
    Generates an analytical Gaussian beam pattern in a Tidy3D Far Field Data structure.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    # tidy3d imports
    import tidy3d as td
    import tidy3d.web as web
    # Extract coordinates from the monitor
    x_coords = np.array(proj_monitor.x)
    y_coords = np.array(proj_monitor.y)
    z_dist = proj_monitor.proj_distance
    f0 = np.array(proj_monitor.freqs)[0]
    
    X, Y = np.meshgrid(x_coords - proj_monitor.custom_origin[0], 
                       y_coords - proj_monitor.custom_origin[1], 
                       indexing='ij')
    
    E_mag = np.exp(-(X**2 + Y**2) / (waist_radius**2))
    
    wavelength = td.C_0 / f0
    k = 2 * np.pi / wavelength
    phase = np.exp(1j * k * z_dist)

    Etheta_val = (E_mag * phase).reshape(len(x_coords), len(y_coords), 1, 1)

    # Package into Tidy3D DataArrays
    coords = dict(
        x=x_coords,
        y=y_coords,
        z=np.array([z_dist]),
        f=np.array([f0]),
    )
    
    Etheta_da = td.FieldProjectionCartesianDataArray(Etheta_val, coords=coords)
    zero_da = td.FieldProjectionCartesianDataArray(np.zeros_like(Etheta_val), coords=coords)

    return td.FieldProjectionCartesianData(
        monitor=proj_monitor,
        Er=zero_da,
        Etheta=Etheta_da,
        Ephi=zero_da,
        Hr=zero_da,
        Htheta=zero_da,
        Hphi=zero_da,
        projection_surfaces=proj_monitor.projection_surfaces,
    )
