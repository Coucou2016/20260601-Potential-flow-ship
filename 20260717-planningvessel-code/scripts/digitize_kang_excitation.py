"""Extract the blue HOPM amplitude curve, never experimental markers or phases."""
import argparse
import hashlib
import json
from pathlib import Path
import fitz
import numpy as np
import pandas as pd


def run(pdf, out):
    expected = '82c16b2b268679b86dfb0b6ec1fc4e7e24dd4e7e5dd517d3596fdc63eecc29e5'
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != expected:
        raise ValueError('Source PDF hash mismatch')
    out.mkdir(parents=True, exist_ok=False)
    with fitz.open(pdf) as document:
        pix = document[193].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).astype(float)
    # Pixel coordinates refer to the full, unrescaled PDF raster. Axis baselines
    # have a small scan tilt, included by interpolating the zero ordinate.
    axes = {'heave': dict(x0=344., x10=1054., y0=2402., y10=2396., ytop=1552., top=20.),
            'pitch': dict(x0=1210., x10=1920., y0=2397., y10=2397., ytop=1547., top=3.)}
    contract = dict(source=str(pdf), sha256=expected, pdf_page_one_based=194, figure='7.14',
        source_curve='HOPM numerical calculation, NOT experimental data', axes=axes,
        omega_encounter_nondimensional=[2., 3., 4., 5., 6.],
        pixel_reading_bound=4, status='DIGITIZATION_CANDIDATE_NOT_PHYSICAL_ACCEPTANCE',
        extractor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        color_rule='B>R+25 and B>G+30; three-column sampling; at least three rows',
        frequency_definition='omega_e*sqrt(L/g)',
        force_definition='abs(F3)/(rho*g*volume*wave_amplitude/L)',
        moment_definition='abs(F5)/(rho*g*volume*wave_amplitude)',
        force_scope='Total excitation amplitude, not pure diffraction; no phase recovered')
    (out/'contract.json').write_text(json.dumps(contract, indent=2))
    rows = []
    for component, a in axes.items():
        for omega in contract['omega_encounter_nondimensional']:
            x = int(round(a['x0'] + omega/10*(a['x10']-a['x0'])))
            strip = rgb[1740:2395, x-1:x+2]
            blue = (strip[:,:,2] > strip[:,:,0]+25) & (strip[:,:,2] > strip[:,:,1]+30)
            ys = np.flatnonzero(blue.any(axis=1)) + 1740
            if len(ys) < 3:
                rows.append(dict(component=component, omega_e_sqrt_L_g=omega,
                    status='NO_RESOLVED_BLUE_TRACE', pixel_x=x))
                continue
            # More than one separated trace is ambiguous; do not choose by fit.
            if np.max(np.diff(ys), initial=0) > 8 or np.ptp(ys) > 30:
                raise ValueError(f'Ambiguous trace: {component} {omega}: {ys}')
            y = float(np.median(ys))
            baseline = a['y0'] + omega/10*(a['y10']-a['y0'])
            scale = (a['y0']-a['ytop'])/a['top']
            rows.append(dict(component=component, omega_e_sqrt_L_g=omega,
                status='EXTRACTED_PENDING_VISUAL_AUDIT',
                amplitude=(baseline-y)/scale, pixel_x=x, pixel_y=y,
                trace_y_min=int(ys.min()), trace_y_max=int(ys.max()),
                amplitude_reading_bound=(4+np.ptp(ys)/2)/scale,
                frequency_reading_bound=4*10/(a['x10']-a['x0'])))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'amplitudes.csv', index=False)
    print(frame.to_string(index=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.pdf, a.out)
