from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
ranks = comm.Get_size()

import os
import sys
import numpy as np
import opencosmo as oc
from opencosmo.analysis import create_yt_dataset, visualize_halo, halo_projection_array
import matplotlib.pyplot as plt
plt.rcParams['mathtext.fontset'] = 'cm'
from matplotlib import cm
from matplotlib import colors as mcolors
from matplotlib.colors import LogNorm, SymLogNorm, CenteredNorm
import yt
from unyt import unyt_quantity, unyt_array
from yt.units import Mpc, km, s
import pyxsim
from astropy.table import Table


from scipy.optimize import curve_fit
from colossus.cosmology import cosmology
from colossus.halo import profile_nfw, profile_einasto
from colossus.lss import peaks


def get_xoff(halo_properties):
    xoff = np.sqrt(  (halo_properties["sod_halo_com_x"]-halo_properties["fof_halo_center_x"])**2 + \
                     (halo_properties["sod_halo_com_y"]-halo_properties["fof_halo_center_y"])**2 + \
                     (halo_properties["sod_halo_com_z"]-halo_properties["fof_halo_center_z"])**2 ) \
                     / halo_properties["sod_halo_radius"]

    xoff_gas = np.sqrt(  (halo_properties["sod_halo_com_x_gas"]-halo_properties["fof_halo_center_x"])**2 + \
                     (halo_properties["sod_halo_com_y_gas"]-halo_properties["fof_halo_center_y"])**2 + \
                     (halo_properties["sod_halo_com_z_gas"]-halo_properties["fof_halo_center_z"])**2 ) \
                     / halo_properties["sod_halo_radius"]

    return {"xoff": xoff, "xoff_gas": xoff_gas}

def Mdiff_gal(ds, c='k', save=True, fig=None, ax=None, label=None, halo_label=None):

    #galaxy_properties = ds["galaxy_properties"].data
    #for halo_properties in ds.halos(): #ds.objects()

    Mhalo = []
    Mdiff = []
    Mdiff_norm = []
    xoff = []

    for ds_i in ds.objects():
        halo_properties, galaxy_properties = ds_i["halo_properties"], ds_i["galaxy_properties"].data
        xh, yh, zh = halo_properties["fof_halo_center_x"],halo_properties["fof_halo_center_y"],halo_properties["fof_halo_center_z"]
        xg, yg, zg = galaxy_properties["gal_com_x"],galaxy_properties["gal_com_y"],galaxy_properties["gal_com_z"]
        Mh = halo_properties["sod_halo_mass"]
        Mg = galaxy_properties["gal_mass_star"]

        if len(Mg) == 0:
            continue

        if len(Mg) > 1:
            Mgsort = np.sort(Mg.value) 
            Mdiff_i = Mgsort[-1] - Mgsort[-2]
            #print(f"{Mdiff_i.value:1.2e}")

            Mg_max = Mgsort[-1]

            if halo_label == "cluster":
                if Mg_max < 5e11:
                    continue
            elif halo_label == "group":
                if Mg_max < 1e11:
                    continue

            Mhalo.append(Mh.value)
            Mdiff.append(Mdiff_i)
            Mdiff_norm.append(Mdiff_i / Mg_max)
            xoff.append(halo_properties["xoff"].value)

        else:
            #Mdiff = 0
            continue


    #plotting

    if fig is None:
        fig, [ax1, ax2] = plt.subplots(1,2)

    else:
        [ax1, ax2] = ax

    # TODO make this a 2D histogram instead for more statistics
    ax1.scatter(Mdiff, xoff, c=c, alpha=0.4, s=2, label=label)
    ax1.set(xlabel=r"$\Delta M_\mathrm{gal}\ \left[ M_\odot \right]$",
           ylabel=r"$\Delta x_\mathrm{off}$",
           ylim = [0,0.3],
           xscale="log",
           xlim = [5e10, 3e12],
           #yscale="log",
           #title=fr"$M_\mathrm{{200c}} = [{mass_bin[0]:1.1e}, {mass_bin[1]:1.1e}) M_\odot$",
           box_aspect=1,
    )
    ax2.scatter(Mdiff_norm, xoff, c=c, alpha=0.4, s=2, label=label)
    ax2.set(xlabel=r"$\frac{\Delta M_\mathrm{gal}}{M_\mathrm{gal,max}}$",
           ylabel=r"$\Delta x_\mathrm{off}$",
           ylim=[0,0.3],
           xlim=[0.05,1],
           xscale="log",
           #yscale="log",
           #title=fr"$M_\mathrm{{200c}} = [{mass_bin[0]:1.1e}, {mass_bin[1]:1.1e}) M_\odot$",
           box_aspect=1,
    )

    if label is not None:
        ax1.legend()

    fig.tight_layout()

    if save:
        fig.savefig(f"plots/delta_Mgal_most_massive.png", bbox_inches="tight")
    else:
        return fig, [ax1, ax2], [Mdiff_norm, xoff]

def Mdiff_split(ds):

    mass_bins = [[5e12,1e14],[1e14, 1e16]]
    colors = ['blue', 'red']
    labels = [r"$5\times10^{12} - 10^{14}\,\,M_\odot$", r"$10^{14}-10^{16}\,\,M_\odot$"]

    fig, ax = plt.subplots(1,2)

    for i, mass_bin in enumerate(mass_bins):
        print(mass_bin)
        ds_i = ds.filter(oc.col("sod_halo_mass") > mass_bin[0], 
                       oc.col("sod_halo_mass") <= mass_bin[1])

        fig, ax, _ = Mdiff_gal(ds_i, c=colors[i], save=False, fig=fig, ax=ax, label=labels[i])


    fig.savefig(f"plots/delta_Mgal_most_massive.png", bbox_inches="tight")


def Mdiff_binned_xoff_hists(ds, cumulative=False):

    bins = np.linspace(0.05, 1, 20)
    xoff_bins = np.linspace(0,0.3,30)

    fig, ax = plt.subplots(1,1)

    ds_group = ds.filter( oc.col("sod_halo_mass") > 5e12, oc.col("sod_halo_mass") < 1e14 )
    ds_cluster = ds.filter( oc.col("sod_halo_mass") > 1e14)

    _, _, [Mdiff_norm_g, xoff_g] = Mdiff_gal(ds_group, save=False)
    _, _, [Mdiff_norm_c, xoff_c] = Mdiff_gal(ds_cluster, save=False)

    Mdiff_norm_g, xoff_g = np.array(Mdiff_norm_g), np.array(xoff_g)
    Mdiff_norm_c, xoff_c = np.array(Mdiff_norm_c), np.array(xoff_c)
    for i in range(len(bins)-1):
        bin_low, bin_high = bins[i], bins[i+1]

        for Mdiff_norm, xoff, color, label in zip([Mdiff_norm_g, Mdiff_norm_c],[xoff_g, xoff_c], ["blue", "red"], ["groups", "clusters"]):

            xoff_i = xoff[ (bin_low < Mdiff_norm) * (Mdiff_norm <= bin_high) ]

            counts, _ = np.histogram(xoff_i, bins=xoff_bins, density=False)

            if ranks > 1:
                #if counts is not None:
                    #print(f"[mass bin {i}, rank {rank}] -- {sum(counts)} halos", flush=True)
                counts = comm.reduce(counts, op=MPI.SUM, root=0)
                if cumulative:
                    counts = np.cumsum(counts)



            if rank == 0:
                #ax.bar(0.5*(xoff_bins[1:]+xoff_bins[:-1]), counts, width=xoff_bins[1:]-xoff_bins[:-1], align="center", label=label, color=color, alpha=0.5)
                ax.step(0.5*(xoff_bins[1:]+xoff_bins[:-1]), counts, where="mid", label=label, color=color)
                #ax.axvline(0.07, color='k', linestyle='--', linewidth=1)
                ax.set(xlabel=r"$x_\mathrm{off}$",
                       ylabel="N",
                       yscale="log",
                       xlim = [0,0.3],
                       title=fr"$\frac{{\Delta M_{{12}}}}{{M_1}} = ({bin_low:1.2f}, {bin_high:1.2f}]$",
                       #box_aspect=1,
                )

            comm.Barrier()

        if rank == 0:
            ax.set(xlabel=r"$x_\mathrm{off}$",
                   ylabel="N",
                   yscale="log",
                   xlim = [0,0.3],
                   title=fr"$\frac{{\Delta M_{{12}}}}{{M_1}} = [{bin_low:1.2f}, {bin_high:1.2f})$",
                   #box_aspect=1,
            )
            ax.legend()

            fig.tight_layout()
            fig.savefig(f"plots/xoff_hists/xoff_hist_Mdiff_bin_{i:03d}", bbox_inches="tight")

        ax.clear()


def core_entropy_hists(ds, plot_relaxed=True, plot_unrelaxed=True, normalize_entropy=False, mass_bins = [[1e12, 1e16]]):

    fig, axes = plt.subplots(len(mass_bins),1 )

    if len(mass_bins) == 1:
        axes = [axes]

    def get_Kdelta(Mgas, R, T):
        ne = Mgas / (1.14 * 1.67e-24) / ((4/3)*np.pi*R**3) * (1.989e33 / (3.086e24)**3)

        return 8.61733326e-8 * T * ne**-(2/3)

    for i in range(len(mass_bins)):
        mass_bin = mass_bins[i]
        print(f"{mass_bin[0]:1.2e}, {mass_bin[1]:1.2e}")
        ds = ds.filter(oc.col("sod_halo_core_entropy") > 0, 
                       oc.col("sod_halo_mass") > mass_bin[0], 
                       oc.col("sod_halo_mass") < mass_bin[1]
        )

        ax = axes[i]

        entropy_total = ds.data["sod_halo_core_entropy"].value
        if normalize_entropy:
            bins = np.geomspace(1e-2, 1e2, 32)

            factor = 1/get_K500( ds.data["sod_halo_MGas500c"].value, ds.data["sod_halo_R500c"].value, ds.data["sod_halo_T500c"].value )

        else:
            bins = np.geomspace(1e1, 1e5, 32)
            factor=1

        ax.hist(entropy_total*factor, bins=bins, density=True, histtype="step", color="black", label="all halos")

        if plot_relaxed:
            ds_relaxed = ds.filter(oc.col("xoff") <= 0.07).data
            ds_relaxed_gas = ds.filter(oc.col("xoff_gas") <= 0.07).data
            entropy_r = ds_relaxed["sod_halo_core_entropy"].value
            entropy_rg = ds_relaxed_gas["sod_halo_core_entropy"].value

            if normalize_entropy:
                entropy_r  /= get_Kdelta(ds_relaxed["sod_halo_MGas500c"].value, ds_relaxed["sod_halo_R500c"].value, ds_relaxed["sod_halo_T500c"].value)
                entropy_rg /= get_Kdelta(ds_relaxed_gas["sod_halo_MGas500c"].value, ds_relaxed_gas["sod_halo_R500c"].value, ds_relaxed_gas["sod_halo_T500c"].value)

            ax.hist(entropy_r, bins=bins, density=True, histtype="step", color="blue", label=r"$x_\mathrm{off} \leq 0.07$")
            ax.hist(entropy_rg, bins=bins, density=True, histtype="step", color="blue", linestyle='--', label=r"$x_\mathrm{off, gas} \leq 0.07$")

        if plot_unrelaxed:
            ds_unrelaxed = ds.filter(oc.col("xoff") > 0.07).data
            ds_unrelaxed_gas = ds.filter(oc.col("xoff_gas") > 0.07).data
            entropy_u = ds_unrelaxed["sod_halo_core_entropy"].value
            entropy_ug = ds_unrelaxed_gas["sod_halo_core_entropy"].value

            if normalize_entropy:
                entropy_u  /= get_Kdelta(ds_unrelaxed["sod_halo_MGas500c"].value, ds_unrelaxed["sod_halo_R500c"].value, ds_unrelaxed["sod_halo_T500c"].value)
                entropy_ug /= get_Kdelta(ds_unrelaxed_gas["sod_halo_MGas500c"].value, ds_unrelaxed_gas["sod_halo_R500c"].value, ds_unrelaxed_gas["sod_halo_T500c"].value)
            
            ax.hist(entropy_u, bins=bins, density=True,  histtype="step", color="red", label=r"$x_\mathrm{off} > 0.07$")
            ax.hist(entropy_ug, bins=bins, density=True,  histtype="step", color="red", linestyle = '--', label=r"$x_\mathrm{off, gas} > 0.07$")

        if normalize_entropy:
            xlabel=r"$\frac{<K>_\mathrm{core}}{K_\mathrm{500c}}$"
        else:
            xlabel=r"$<K>_\mathrm{core}\ \left[ \mathrm{K}e\mathrm{V\,cm^2} \right]$"

        ax.set(xlabel=xlabel,
               ylabel="PDF",
               xscale="log",
               yscale="log",
               #title=fr"$M_\mathrm{{200c}} = [{mass_bin[0]:1.1e}, {mass_bin[1]:1.1e}) M_\odot$",
               #box_aspect=1,
        )

    axes[0].legend()

    fig.tight_layout()

    if normalize_entropy:
        fig.savefig("plots/core_entropy_hists_norm.png")

    else:
        fig.savefig("plots/core_entropy_hists.png")

def CM_relation(ds, mass_bins, relaxed_definitions = ["xoff"], rel_kwargs={}, unrel_kwargs={}):

    fig, ax = plt.subplots(1,1)

    C_rel = {}
    C_unrel = {}
    M = []

    for i in range(len(mass_bins)-1):
        for relaxed_definition in relaxed_definitions:
            if i == 0:
                C_rel[relaxed_definition]   = []
                C_unrel[relaxed_definition] = []

            mlow, mhigh = mass_bins[i], mass_bins[i+1]

            ds_i = ds.filter(oc.col("sod_halo_mass") > mlow, oc.col("sod_halo_mass") < mhigh)

            if relaxed_definition == "xoff":
                hp_i_r  = ds_i.filter(oc.col("xoff") <= 0.07)["halo_properties"].get_data()
                hp_i_ur = ds_i.filter(oc.col("xoff") > 0.07)["halo_properties"].get_data()

                C_i_r = np.median(hp_i_r["sod_halo_cdelta"])
                C_i_ur = np.median(hp_i_ur["sod_halo_cdelta"])

            elif relaxed_definition == "Mdiff_gal":
                _, _, [Mdiff_i,  _] = Mdiff_gal(ds_i, save=False)

                idx_rel = Mdiff_i > 0.5

                C_i_r = np.median(ds_i["sod_halo_concentration"][idx_rel])
                C_i_ur = np.median(ds_i["sod_halo_concentration"][~idx_rel])

            C_rel[relaxed_definition].append(C_i_r)
            C_unrel[relaxed_definition].append(C_i_ur)
            M.append(np.median(ds_i["halo_properties"].data["sod_halo_mass"]))

    for relaxed_definition in relaxed_definitions:
        ax.scatter(M, C_rel[relaxed_definition], *rel_kwargs[relaxed_definition])
        ax.scatter(M, C_unrel[relaxed_definition], *unrel_kwargs[relaxed_definition])

    ax.set(
        xlabel = r"$M_\mathrm{200c}$",
        ylabel = r"$C_\mathrm{200c}$",
        xlim = [1e12, 1e16],
        ylim = [0,10],
        xscale = "log",
    )

    ax.legend()

    fig.tight_layout()
    fig.savefig("plots/CM_relation.png", bbox_inches="tight") 






if __name__ == "__main__":
    z=0 # 1 2
    step = 624 #205 # 310 205
    Nbins = 40
    savedir = f"plots/{step}"
    os.makedirs(savedir, exist_ok=True)
    
    dir_hydro = "/lustre/orion/hep142/proj-shared/INCITE/hydro/HDF5_data/run_hydro/output/"
    dir_go = "/lustre/orion/hep142/proj-shared/INCITE/gravonly/HDF5_data/run_go/output/"

    halo_properties_hydro = f"{dir_hydro}/step_{step}/haloproperties/m000p-{step}.haloproperties.0.hdf5"
    halo_profiles_hydro = f"{dir_hydro}/step_{step}/sodpropertybins/m000p-{step}.sodpropertybins.0.hdf5"
    halo_particles_hydro = f"{dir_hydro}/step_{step}/sodbighaloparticles/m000p-{step}.sodbighaloparticles.0.hdf5"
    galaxy_properties_hydro = f"{dir_hydro}/step_{step}/galaxyproperties/m000p-{step}.galaxyproperties.0.hdf5"
    
    #halo_properties_hydro = f"{dir_hydro}/step_{step}/haloproperties/m000p-{step}.haloproperties.hdf5"
    #halo_profiles_hydro = f"{dir_hydro}/step_{step}/sodpropertybins/m000p-{step}.sodpropertybins.hdf5"
    #halo_particles_hydro = f"{dir_hydro}/step_{step}/sodbighaloparticles/m000p-{step}.sodbighaloparticles.hdf5"
    #galaxy_properties_hydro = f"{dir_hydro}/step_{step}/galaxyproperties/m000p-{step}.galaxyproperties.hdf5"

    halo_properties_go = f"{dir_go}/step_{step}/haloproperties/m000p-{step}.haloproperties.0.hdf5"
    halo_profiles_go = f"{dir_go}/step_{step}/sodpropertybins/m000p-{step}.sodpropertybins.0.hdf5"
    halo_particles_go =f"{dir_hydro}/step_{step}/sodbighaloparticles/m000p-{step}.sodbighaloparticles.0.hdf5" 

    '''
    ds = oc.open(halo_properties_hydro, halo_particles_hydro, halo_profiles_hydro)
    ds = ds.evaluate(get_xoff, 
                     insert=True, 
                     #vectorize=True,
                     halo_properties=[
                        "fof_halo_center_x",
                        "fof_halo_center_y",
                        "fof_halo_center_z",
                        "sod_halo_com_x",
                        "sod_halo_com_y",
                        "sod_halo_com_z",
                        "sod_halo_com_x_gas",
                        "sod_halo_com_y_gas",
                        "sod_halo_com_z_gas",
                        "sod_halo_radius"
                    ]
         )
    '''
    fgas_range = [0, 1.0]
    chi_range = [0.05, 100]

    #mass_bins = [
    #    [1e12,1e13],
    #    [5e13,1e14],
    #    [1e14,5e14],
    #    [5e14,1e15]
    #]

    #mass_bins = [[1e14, 5e14]]

    #core_entropy_hists(ds["halo_properties"], mass_bins=mass_bins, normalize_entropy=True, plot_relaxed=True, plot_unrelaxed=True)

    ds_gal = oc.open(halo_properties_hydro, galaxy_properties_hydro).filter(oc.col("sod_halo_mass") > 5e12)#.take(1000)
    ds_gal = ds_gal.evaluate(get_xoff, 
                     insert=True, 
                     #vectorize=True,
                     halo_properties=[
                        "fof_halo_center_x",
                        "fof_halo_center_y",
                        "fof_halo_center_z",
                        "sod_halo_com_x",
                        "sod_halo_com_y",
                        "sod_halo_com_z",
                        "sod_halo_com_x_gas",
                        "sod_halo_com_y_gas",
                        "sod_halo_com_z_gas",
                        "sod_halo_radius"
                    ]
    )
    #Mdiff_split(ds_gal)
    #Mdiff_binned_xoff_hists(ds_gal, cumulative=True)
    #Mdiff_gal(ds_gal)


    mass_bins = np.geomspace(5e12, 1e16, 4)

    rel_kwargs = {
        "xoff": {
            "color": "k",
            "label": r"$x_\mathrm{off}$",
            "marker": "o",
        },
        "Mdiff_gal": {
            "color": "k",
            "label": r"$\frac{\Delta M_{12}}{M_1}$",
            "marker": "X",
        }
    }
    
    unrel_kwargs = {
        "xoff": {
            "color": "k",
            #"label": r"$x_\mathrm{off}$",
            "marker": "o",
            "fillstyle": "none"
        },
        "Mdiff_gal": {
            "color": "k",
            #"label": r"$\frac{\Delta M_{12}}{M_1}$",
            "marker": "X",
            "fillstyle": "none"
        }
    }

    CM_relation(ds_gal, mass_bins, rel_kwargs=rel_kwargs, unrel_kwargs=unrel_kwargs)
