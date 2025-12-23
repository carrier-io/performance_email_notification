# Copyright 2019 getcarrier.io
# Licensed under the Apache License, Version 2.0

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

plt.rcParams.update({'font.size': 14})

YELLOW = '#FFA400'


def _setup_chart_style(ax, x_max, y_max, datapoints):
    """Configure common chart styling."""
    plt.xlim(0, x_max + 1)
    plt.ylim(0, y_max + y_max * 0.15)
    ax.grid(color="#E3E3E3")
    ax.set_xlabel(datapoints['x_axis'])
    ax.set_ylabel(datapoints['y_axis'])
    ax.set_xticklabels(datapoints.get('labels', [str(dp) for dp in datapoints['values']]))
    ax.set_xticks(datapoints['values'])
    
    for spine in ['bottom']:
        ax.spines[spine].set_color('#E3E3E3')
    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_color('#ffffff')


def _annotate_values(ax, values, x_coords, y_offset_pct=0.05):
    """Add value annotations above data points."""
    y_max = max(values) if values else 0
    for index, value in enumerate(values):
        ax.annotate(str(value), xy=(x_coords[index], value + y_max * y_offset_pct))


def alerts_linechart(datapoints):
    """Generate alert trends line chart."""
    fig, ax = plt.subplots(figsize=(datapoints['width'], datapoints['height'] * 1.5), 
                          dpi=72, facecolor='w')
    
    x_max = max(datapoints['values'])
    y_max = max(datapoints['keys'])
    
    ax.plot(datapoints['values'], datapoints['keys'], '--', linewidth=2,
            label=datapoints['label'], color=YELLOW)
    ax.plot(datapoints['values'], datapoints['keys'], 'o', linewidth=4, color=YELLOW)
    
    _annotate_values(ax, datapoints['keys'], datapoints['values'])
    _setup_chart_style(ax, x_max, y_max, datapoints)
    
    fig.savefig(datapoints['path_to_save'], bbox_inches='tight')
    plt.close()


def barchart(datapoints):
    """Generate comparison bar chart with positive/negative values."""
    fig, ax = plt.subplots(figsize=(datapoints['width'] * 2, datapoints['height'] * 2), 
                          dpi=300, facecolor='w')
    
    bar_configs = [
        (datapoints['utility_keys'], datapoints['utility_request'], 'white', None, None),
        (datapoints['green_keys'], datapoints['green_request'], 'green', 
         datapoints['green_request_name'], 1),
        (datapoints['red_keys'], datapoints['red_request'], 'red', 
         datapoints['red_request_name'], -1),
        (datapoints['yellow_keys'], datapoints['yellow_request'], 'orange', 
         datapoints['yellow_request_name'], -1)
    ]
    
    for keys, values, color, names, multiplier in bar_configs:
        plt.bar(keys, values, color=color)
        
        if names and multiplier:
            for index, value in enumerate(values):
                if multiplier > 0:
                    ax.annotate(f" {value} s", xy=(int(keys[index]) - 0.1, value + 0.05),
                              rotation=90, verticalalignment='bottom')
                    ax.annotate(f"{names[index]} ", xy=(int(keys[index]) - 0.1, -0.1),
                              rotation=90, verticalalignment='top')
                else:
                    ax.annotate(f"{float(value) * -1} s ", xy=(int(keys[index]) - 0.1, value - 0.05),
                              rotation=90, verticalalignment='top')
                    ax.annotate(f" {names[index]}", xy=(int(keys[index]) - 0.1, 0.1),
                              rotation=90, verticalalignment='bottom')
    
    plt.yscale('symlog', base=2, linthresh=5.0)
    ax.get_yaxis().set_major_formatter(ScalarFormatter())
    ax.set_frame_on(False)
    ax.axhline(linewidth=1, color='black')
    ax.set_xticklabels([])
    ax.set_xticks([])
    ax.set_yticklabels([])
    ax.set_yticks([])
    
    fig.savefig(datapoints['path_to_save'], bbox_inches='tight')
    plt.close()


def ui_comparison_linechart(datapoints):
    """Generate UI performance comparison stacked bar chart."""
    fig, ax = plt.subplots(figsize=(datapoints['width'] * 2, datapoints['height'] * 2), 
                          dpi=300, facecolor='w')
    
    b1 = ax.bar(datapoints['keys'], datapoints['latency_values'], color='#7EB26D')
    b2 = ax.bar(datapoints['keys'], datapoints['transfer_values'],
                bottom=datapoints['latency_values'], color='#EAB839')
    b3 = ax.bar(datapoints['keys'], datapoints['tbt_values'],
                bottom=[x + y for x, y in zip(datapoints['transfer_values'], 
                                               datapoints['latency_values'])],
                color='#6ED0E0')
    b4 = ax.bar(datapoints['keys'], datapoints['ttl_values'],
                bottom=[sum(x) for x in zip(datapoints['transfer_values'],
                                            datapoints['latency_values'],
                                            datapoints['tbt_values'])],
                color='#EF843C')
    
    ax.legend((b1[0], b2[0], b3[0], b4[0]), ('latency', 'transfer', 'tbt', 'ttl'), 
             loc='upper right')
    ax.set_xlabel(datapoints['x_axis'])
    ax.set_ylabel(datapoints['y_axis'])
    ax.set_title(datapoints['title'])
    plt.xlim(0, len(datapoints['keys']) + 1)
    ax.set_xticklabels(datapoints.get('labels', [str(dp) for dp in datapoints['keys']]))
    ax.set_xticks(datapoints['keys'])
    
    fig.savefig(datapoints['path_to_save'], bbox_inches='tight')
    plt.close()


def _plot_metrics(ax, datapoints, metrics_config):
    """Plot metrics that have data and return max values."""
    y_max = x_max = 0
    x_max = max(datapoints['values'])
    plot_lines = []
    
    for metric, label in metrics_config:
        has_data_key = f'{metric}_has_data'
        if datapoints.get(has_data_key, True) and metric in datapoints and datapoints[metric]:
            y_max = max(max(datapoints[metric]), y_max)
            line, = ax.plot(datapoints['values'], datapoints[metric], linewidth=2, label=label)
            plot_lines.append((line, metric))
    
    for line, metric in plot_lines:
        _annotate_values(ax, datapoints[metric], datapoints['values'])
    
    if plot_lines:
        ax.legend(loc='upper left')
    
    return x_max, y_max


def ui_metrics_chart_pages(datapoints):
    """Generate UI page metrics trend chart."""
    fig, ax = plt.subplots(figsize=(datapoints['width'], datapoints['height'] * 1.5), 
                          dpi=72, facecolor='w')
    
    metrics_config = [('ttfb', 'TTFB'), ('tbt', 'TBT'), ('lcp', 'LCP')]
    x_max, y_max = _plot_metrics(ax, datapoints, metrics_config)
    _setup_chart_style(ax, x_max, y_max, datapoints)
    
    fig.savefig(datapoints['path_to_save'], bbox_inches='tight')
    plt.close()


def ui_metrics_chart_actions(datapoints):
    """Generate UI action metrics trend chart."""
    fig, ax = plt.subplots(figsize=(datapoints['width'], datapoints['height'] * 1.5), 
                          dpi=72, facecolor='w')
    
    metrics_config = [('cls', 'CLS'), ('tbt', 'TBT'), ('inp', 'INP')]
    x_max, y_max = _plot_metrics(ax, datapoints, metrics_config)
    _setup_chart_style(ax, x_max, y_max, datapoints)
    
    fig.savefig(datapoints['path_to_save'], bbox_inches='tight')
    plt.close()

