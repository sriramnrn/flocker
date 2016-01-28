# Copyright ClusterHQ Inc.  See LICENSE file for details.

import argparse
import csv
import itertools
import json


WALL_CLOCK_KEY = u'-- WALL --'


HEADERS = [
    u'FlockerVersion',
    u'Nodes',
    u'Containers',
    u'ControlServiceCPUSteady',
    u'DatasetAgentCPUSteady',
    u'ContainerAgentCPUSteady',
    u'ControlServiceCPUReadLoad',
    u'DatasetAgentCPUReadLoad',
    u'ContainerAgentCPUReadLoad',
    u'ControlServiceCPUWriteLoad',
    u'DatasetAgentCPUWriteLoad',
    u'ContainerAgentCPUWriteLoad',
    u'ContainerAdditionConvergence',
]


def write_csv(results, filename):
    with open(filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(results)


def filter_counts(results, count, count_value):
    return [r for r in results if r['control_service'][count] == count_value]


def get_counts(results, key):
    counts = [r['control_service'][key] for r in results]
    return list(set(counts))


def mean(values):
    if len(values) > 0:
        return sum(values) / len(values)
    return None


def cputime_for_process(results, process, scenario, fn=mean):
    process_results= itertools.ifilter(
        lambda r: r['metric']['type'] == 'cputime'
        and r['process'] == process
        and r['scenario']['type'] == scenario,
        results
    )
    values = [r['value'] / r['wallclock'] for r in process_results]
    return fn(values)


def wallclock_for_operation(results, operation, fn=mean):
    operation_results = itertools.ifilter(
        lambda r: r['metric']['type'] == 'wallclock'
        and r['operation']['type'] == operation,
        results
    )
    values = [r['value'] for r in operation_results]
    return fn(values)


def flatten(results):
    flattened = []
    common = dict(
        [(k, results.get(k)) for k in results.iterkeys() if k != 'samples']
    )

    metric_type = results['metric']['type']

    for sample in results['samples']:
        if metric_type == 'cputime':
            for ip, data in sample['value'].iteritems():
                wall_time = data[WALL_CLOCK_KEY]
                for process, value in data.iteritems():
                    if process != WALL_CLOCK_KEY:
                        doc = dict(common)
                        doc['node_ip'] = ip
                        doc['process'] = process
                        doc['value'] = value
                        doc['wallclock'] = wall_time
                        flattened.append(doc)
        elif metric_type == 'wallclock':
            doc = dict(common)
            doc['value'] = sample['value']
            flattened.append(doc)
    return flattened


def parse_args(args):
    parser = argparse.ArgumentParser(
        description="Produce CSV from benchmarking results"
    )
    parser.add_argument("files", nargs="*", type=argparse.FileType(),
                        help="Input JSON files to be processed")

    return parser.parse_args(args).files


def main(args):
    files = parse_args(args)
    results = []
    for f in files:
        results.extend(flatten(json.load(f)))

    summary = []
    node_counts = get_counts(results, 'node_count')
    container_counts = get_counts(results, 'container_count')
    for node_count, container_count in itertools.product(
        node_counts, container_counts
    ):
        node_results = filter_counts(results, 'node_count', node_count)
        container_results = filter_counts(
            node_results, 'container_count', container_count
        )
        result = {
            u'Nodes': node_count,
            u'Containers': container_count,
            u'ControlServiceCPUSteady':
                cputime_for_process(container_results, 'flocker-control', 'no-load'),
            u'ControlServiceCPUReadLoad':
                cputime_for_process(container_results, 'flocker-control', 'read-request-load'),
            u'ControlServiceCPUWriteLoad':
                cputime_for_process(container_results, 'flocker-control', 'write-request-load'),
            u'DatasetAgentCPUSteady':
                cputime_for_process(container_results, 'flocker-dataset', 'no-load'),
            u'DatasetAgentCPUReadLoad':
                cputime_for_process(container_results, 'flocker-dataset', 'read-request-load'),
            u'DatasetAgentCPUWriteLoad':
                cputime_for_process(container_results, 'flocker-dataset', 'write-request-load'),
            u'ContainerAgentCPUSteady':
                cputime_for_process(container_results, 'flocker-contain', 'no-load'),
            u'ContainerAgentCPUReadLoad':
                cputime_for_process(container_results, 'flocker-contain', 'read-request-load'),
            u'ContainerAgentCPUWriteLoad':
                cputime_for_process(container_results, 'flocker-contain', 'write-request-load'),
            u'ContainerAdditionConvergence':
                wallclock_for_operation(container_results, 'create-container'),
        }
        summary.append(result)
    write_csv(summary, 'results.csv')
