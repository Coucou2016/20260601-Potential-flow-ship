import numpy as np
import os
import shutil
import sys
import matplotlib.pyplot as plt
from os.path import exists

with_plots = False

def plot_force_or_motion(stub, extension):
    plot_counter = 0
    resp_moedes = []
    file_pt = open(stub + extension, "r")
    if extension == ".o2":
        oname = "wvf"
    elif extension == ".o3":
        oname = "rao"
    elif extension == ".o4":
        oname = "sct"
    elif extension == ".o5":
        oname = "fkf"
    file_pt.readline()
    nfreqs = int(file_pt.readline().split()[2].split(":")[1])
    froude = float(file_pt.readline().split()[1].split(":")[1])
    file_pt.readline()
    with file_pt as f:
        vars = [[float(num) for num in line.split()] for line in f]
    vars = np.array(vars)
    fff = len(vars)
    size = int(len(vars) / nfreqs)
    for i in range(size):
        st = i * nfreqs
        en = (i + 1) * nfreqs
        omegas = vars[st:en, 0:2]
        res = vars[st:en, 3:6]
        out_vals = np.c_[omegas, res]
        modes = str(int(vars[st, 2]))
        resp_moedes.append(modes)
        fname = out_folder + oname + modes + ".txt"
        np.savetxt(fname, out_vals, delimiter="\t")
        if with_plots:
            plt.figure(plot_counter)
            plt.plot(out_vals[:, 0], out_vals[:, 4], color="b")
            plt.title(oname + " " + modes)
            plot_counter += 1
            plt.show()
    return resp_moedes


# ---------------------------------------------------------------------
# Folders business
# ---------------------------------------------------------------------
path_to_results = input("Enter path to the results: ")

if not os.path.isdir(path_to_results):
    sys.exit(0)

full_name = path_to_results.split("/")[-1]
underscore_index = full_name.find("_")+1
project_name = full_name[0:underscore_index-1]
out_folder = (
    path_to_results[0: path_to_results.find(
        project_name + "_" + "ow3df")] + project_name + "_ppc/"
)
stub = path_to_results + "/" + project_name
shutil.rmtree(out_folder, ignore_errors=True)
os.makedirs(os.path.dirname(out_folder))
rad_modes = []
resp_modes = []
# ---------------------------------------------------------------------
# Read and store the hydrodynamic coefficients
# ---------------------------------------------------------------------
if exists(stub + ".o1"):
    plot_counter = 0
    file_pt = open(stub + ".o1", "r")
    file_pt.readline()
    nfreqs = int(file_pt.readline().split()[2].split(":")[1])
    froude = float(file_pt.readline().split()[1].split(":")[1])
    with file_pt as f:
        hydros = [[float(num) for num in line.split()] for line in f]
    hydros = np.array(hydros)
    size = int(len(hydros) / nfreqs)
    for i in range(size):
        st = i * nfreqs
        en = (i + 1) * nfreqs
        ome = hydros[st:en, 1]
        ab = hydros[st:en, 4:6]
        cf = np.c_[ome, ab]
        imode = hydros[st, 2].astype(int).astype(str)
        jmode = hydros[st, 3].astype(int).astype(str)
        modes = imode+jmode
        if len(modes)>2:
            modes = imode+'.' + jmode
        rad_modes.append(modes)
        fname = out_folder + "hydros" + modes + ".txt"
        np.savetxt(fname, cf, delimiter="\t")  
        if with_plots:
            plt.figure(plot_counter)
            plt.grid()
            plt.plot(cf[:, 0], cf[:, 1], color="b")
            plot_counter += 1
            plt.title('a'+modes)
            plt.figure(plot_counter)
            plt.grid()
            plt.plot(cf[:, 0], cf[:, 2], color="b")
            plot_counter += 1
            plt.title('b'+modes)
            plt.show()
# ---------------------------------------------------------------------
# Read and store the wave forces
# ---------------------------------------------------------------------
if exists(stub + ".o2"):
    resp_modes = plot_force_or_motion(stub, ".o2")
# ---------------------------------------------------------------------
# Read and store the raos
# ---------------------------------------------------------------------
if exists(stub + ".o3"):
    plot_force_or_motion(stub, ".o3")
# ---------------------------------------------------------------------
# Read and store the scattering forces
# ---------------------------------------------------------------------
if exists(stub + ".o4"):
    plot_force_or_motion(stub, ".o4")
# ---------------------------------------------------------------------
# Read and store the Froude-Krylov forces
# ---------------------------------------------------------------------
if exists(stub + ".o5"):
    plot_force_or_motion(stub, ".o5")
# ---------------------------------------------------------------------
# Read and store the drift forces
# ---------------------------------------------------------------------
if exists(stub + ".o6"):
    file_pt = open(stub + ".o6", "r")
    file_pt.readline()
    nfreqs = int(file_pt.readline().split()[2].split(":")[1])
    froude = float(file_pt.readline().split()[1].split(":")[1])
    file_pt.readline()
    with file_pt as f:
        drifts = [[float(num) for num in line.split()] for line in f]
        drifts = np.array(drifts)
        size = int(len(drifts) / nfreqs)
    for i in range(size):
        st = i * nfreqs
        en = (i + 1) * nfreqs
        ome = drifts[st:en, 0]
        vals = drifts[st:en, 3:6]
        cf = np.c_[ome, vals]
        modes = str(int(drifts[st, 2]))
        fname = out_folder + "drifts" + modes + ".txt"
        np.savetxt(fname, cf, delimiter="\t")

if with_plots:
    # ---------------------------------------------------------------------
    # Plot rimps
    # ---------------------------------------------------------------------
    plot_counter = 0
    for modes in rad_modes:
        file_pt = open(stub + ".rimp" + modes, "r")
        file_pt.readline()
        file_pt.readline()
        with file_pt as f:
            rimps = [[float(num) for num in line.split()] for line in f]
            rimps = np.array(rimps)
            plot_counter += 1
            plt.figure(plot_counter)
            plt.plot(rimps[:, 0], rimps[:, 1], color="b")
            plt.title('rimp' + modes)
            plt.grid() 
            plt.show()
    # ---------------------------------------------------------------------
    # Plot simps
    # ---------------------------------------------------------------------
    plot_counter = 0
    for modes in resp_modes:
        file_pt = open(stub + ".simp" + modes, "r")
        file_pt.readline()
        file_pt.readline()
        with file_pt as f:
            simps = [[float(num) for num in line.split()] for line in f]
            simps = np.array(simps)
            plt.figure(plot_counter)
            plt.plot(simps[:, 0], simps[:, 1], color="b")
            plot_counter += 1
            plt.title('simp' + modes)
            plt.show()
