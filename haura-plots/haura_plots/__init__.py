#!/bin/env python
import json
import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.cm as cm
import matplotlib.colors as mat_col
import matplotlib

from . import util
from . import metrics_plots

def sort_by_o_id(key):
    """
    Access string subslice and first tuple member
    """
    return int(key[0][2:])

def plot_object_distribution(path):
    """
    Plot colorcoded grids to show object distribution
    """
    data = []
    if not os.path.exists(f"{path}/tier_state.jsonl"):
        return

    with open(f"{path}/tier_state.jsonl", 'r', encoding='UTF-8') as state_file:
        data = util.read_jsonl(state_file)
    colors = {
        0: util.WHITE,
        1: util.GREEN,
        2: util.YELLOW,
        3: util.BLUE,
    }
    cmap = mat_col.ListedColormap([x[1] for x in colors.items()])
    labels = np.array(["Not present", "Fastest", "Fast", "Slow"])
    num_ts = 0
    # three groups fixed
    mean_group_vals = [[], [], []]
    for current_timestep in data:
        # Read all names and order
        # Iterate over each tier and add keys to known keys
        keys = []  # Vec<(key, num_tier)>
        num_tier = 1
        for tier in current_timestep:
            for obj in tier["files"]:
                keys.append((obj, num_tier))
            num_tier += 1

        keys.sort(key=sort_by_o_id)

        # old boundaries update when needed
        # seldom accessed 1-2000 (45x45)
        # barely accessed 2001-2300 (18x18)
        # often accessed 2301-2320 (5x5)
        group_1 = [n[1] for n in keys[:4030]]
        group_2 = [n[1] for n in keys[4030:4678]]
        group_3 = [n[1] for n in keys[4678:4728]]

        # Reshape to matrix and fill with zeros if necessary
        group_1 = np.concatenate((np.array(group_1), np.zeros(4096 - len(group_1)))).reshape((64,64))
        group_2 = np.concatenate((np.array(group_2), np.zeros(676 - len(group_2)))).reshape((26,26))
        group_3 = np.concatenate((np.array(group_3), np.zeros(64 - len(group_3)))).reshape((8,8))

        num_group = 0
        fig, axs = plt.subplots(1, 4, figsize=(20,5))
        for group in [group_1, group_2, group_3]:
            subax = axs[num_group]
            mean = group[group > 0].mean()
            mean_group_vals[num_group].append(mean)
            subax.set_title(f"Object mean level: {mean}")
            subax.tick_params(color="white")
            num_group += 1
            im = subax.imshow(group, cmap=cmap)
            im.set_clim(0, 3)
            subax.yaxis.set_ticks([])
            subax.xaxis.set_ticks([])
        #divider = make_axes_locatable(subax)
        #cax = divider.append_axes("right", size="5%", pad=0.05)
        #fig.colorbar(im, cax=cax)
        fmt = matplotlib.ticker.FuncFormatter(lambda x, pos: labels[x])
        ticks = [0, 1, 2, 3]
        fig.colorbar(cm.ScalarMappable(cmap=cmap, norm=mat_col.NoNorm()), format=fmt, ticks=ticks)

        # Plot response times if available
        if 'reqs' in current_timestep[0]:
            times = []
            num_tiers = 0
            for tier in current_timestep:
                num_tiers += 1
                resp_times = 0
                total = 0
                for o_id in tier["reqs"]:
                    resps = tier["reqs"][f"{o_id}"]
                    size = tier["files"][f"{o_id}"][1]
                    for resp in resps:
                        total += 1
                        resp_times += resp["response_time"]["nanos"] / size
                if total != 0:
                    times.append(resp_times / total)
                else:
                    times.append(0)
            x_ticks = np.arange(0, num_tiers)
            width = 0.35
            # convert from nanos to millis
            axs[3].bar(x_ticks, np.array(times) / 1000000, width, label='Access latency', hatch=['.', '+', '/'], color='white', edgecolor='black')
            axs[3].set_title('Mean access latency for timestep')
            axs[3].set_ylabel('Mean latency in ms')
            #axs[3].set_ylim(0, 100)
            axs[3].set_xticks(x_ticks, labels=["Fastest", "Fast", "Slow"])

        fig.savefig(f"{path}/plot_timestep_{num_ts:0>3}.png")
        matplotlib.pyplot.close(fig)
        num_ts += 1

    fig, ax = plt.subplots(figsize=(10,5))
    ax.plot(mean_group_vals[0], color=util.ORANGE, label="Seldomly Accessed Group", marker="o", markevery=10);
    ax.plot(mean_group_vals[1], color=util.LIGHT_BLUE, label="Occassionally Accessed", marker="s", markevery=10);
    ax.plot(mean_group_vals[2], color=util.RED, label="Often Accessed", marker="^", markevery=10);
    # we might want to pick the actual timestamps for this
    ax.set_xlabel("Timestep")
    ax.set_ylabel("Mean object tier")
    ax.set_title("Mean tier of all object groups over time")
    ax.set_ylim((1,3))
    pls_no_cut_off = ax.legend(bbox_to_anchor=(1.0,1.0), loc="upper left")
    fig.savefig(f"{path}/plot_timestep_means.svg", bbox_extra_artists=(pls_no_cut_off,), bbox_inches='tight')

def plot_tier_usage(data, path):
    """
    Plot the utilized space of each storage tier.
    """
    fig, axs = plt.subplots(4, 1, figsize=(10,13))

    # 0 - 3; Fastest - Slowest
    free = [[], [], [], []]
    total = [[], [], [], []]
    # Map each timestep to an individual
    for ts in data:
        tier = 0
        for stat in ts["usage"]:
            free[tier].append(stat["free"])
            total[tier].append(stat["total"])
            tier += 1

    tier = 0
    for fr in free:
        axs[tier].plot((np.array(total[tier]) - np.array(fr)) * 4096 / 1024 / 1024 / 1024, label="Used", marker="o", markevery=200, color=util.BLUE)
        axs[tier].plot(np.array(total[tier]) * 4096 / 1024 / 1024 / 1024, label="Total", marker="^", markevery=200, color=util.GREEN)
        axs[tier].set_ylim(bottom=0)
        axs[tier].set_ylabel(f"{util.num_to_name(tier)}\nCapacity in GiB")
        tier += 1

    fig.legend(loc='center right',handles=axs[0].get_lines())
    fig.savefig(f"{path}/tier_usage.svg")

# TODO: Adjust bucket sizes
def size_buckets(byte):
    if byte <= 64000:
        return 64000
    elif byte <= 256000:
        return 256000
    elif byte <= 1000000:
        return 1000000
    elif byte <= 4000000:
        return 4000000
    else:
        return 1000000000

def bytes_to_lexical(byte):
    if byte >= 1000000:
        return f"{byte/1000/1000}MB"
    return f"{byte/1000}KB"

def plot_filesystem_test():
    dat = pd.read_csv(f"{sys.argv[1]}/filesystem_measurements.csv")
    # groups
    fig, axs = plt.subplots(2,3, figsize=(15,5))
    min_read = 99999999999999999
    min_write = 99999999999999999
    max_read = 0
    max_write = 0
    for n in range(3):
        sizes = dat[dat['group'] == n]['size'].to_numpy()
        reads = {}
        reads_raw = dat[dat['group'] == n]['read_latency_ns'].to_numpy()
        writes = {}
        writes_raw = dat[dat['group'] == n]['write_latency_ns'].to_numpy()
        for (idx, size) in enumerate(sizes):
            if size_buckets(size) not in reads:
                reads[size_buckets(size)] = []
            reads[size_buckets(size)].append(reads_raw[idx])
            if size_buckets(size) not in writes:
                writes[size_buckets(size)] = []
            writes[size_buckets(size)].append(writes_raw[idx])

        sorted_sizes = list(reads)
        sorted_sizes.sort()
        labels = []
        reads_plot = []
        writes_plot = []
        for size in sorted_sizes:
            labels.append(bytes_to_lexical(size))
            a = np.array(reads[size]) / 1000
            min_read = min(min_read, a.min())
            max_read = max(max_read, a.max())
            reads_plot.append(a)
            b = np.array(writes[size]) / 1000
            min_write = min(min_write, b.min())
            max_write = max(max_write, b.max())
            writes_plot.append(b)
        axs[0][n].boxplot(reads_plot, vert=True, labels=labels)
        axs[0][n].set_yscale('log')
        match n:
            case 0:
                axs[0][n].set_title("Seldomly Accessed")
            case 1:
                axs[0][n].set_title("Occassionally Accessed")
            case 2:
                axs[0][n].set_title("Often Accessed")
        axs[0][n].set_ylabel("Read latency (μs)")
        axs[1][n].boxplot(writes_plot, vert=True, labels=labels)
        axs[1][n].set_yscale('log')
        axs[1][n].set_ylabel("Write latency (μs)")

    for n in range(3):
        axs[0][n].set_ylim(min(min_read, min_write),max_read + 10000000)
        axs[1][n].set_ylim(min(min_read, min_write),max_write + 10000000)

    fig.savefig(f"{sys.argv[1]}/filesystem_comp.svg")


def plot_evaluation_latency(path, variant):
    if not os.path.exists(f"{path}/evaluation_{variant}.csv"):
        return

    data = pd.read_csv(f"{path}/evaluation_{variant}.csv");

    fig, ax = plt.subplots(1,1,figsize=(6,4))
    ax.scatter(data['size'][:5000], data['latency_ns'][:5000], marker='x')
    xticks = np.arange(0, 12 * 1024 * 1024 + 1, 2 * 1024 * 1024)
    ax.set_xticks(xticks, [int(x / 1024) for x in xticks])
    ax.set_xlabel("Size in KiB")
    ax.set_ylabel("Latency in ns")
    ax.set_yscale("log")
    label=' | '.join(path.split('/')[-2:])
    ax.set_title(f"Haura - {label}")
    fig.savefig(f"{path}/evaluation_read.svg")

USAGE_HELP="""Please specify an input run directory. If you already completed \
benchmarks they can be found under `results/*`.

Usage:
    haura-plots <path/to/benchmark>
"""

def main():
    if len(sys.argv) < 2:
        print(USAGE_HELP)
        sys.exit(2)
    data = []
    with open(f"{sys.argv[1]}/betree-metrics.jsonl", 'r', encoding="UTF-8") as metrics:
        data = util.read_jsonl(metrics)

    # Plot actions
    metrics_plots.plot_throughput(data, sys.argv[1])
    plot_tier_usage(data, sys.argv[1])
    plot_evaluation_latency(sys.argv[1], "read")
    plot_evaluation_latency(sys.argv[1], "rw")
    plot_object_distribution(sys.argv[1])
    #plot_filesystem_test()

if __name__ == "__main__":
    main()
