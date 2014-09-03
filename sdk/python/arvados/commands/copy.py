#! /usr/bin/env python

# arv-copy [--recursive] [--no-recursive] object-uuid src dst
#
# Copies an object from Arvados instance src to instance dst.
#
# By default, arv-copy recursively copies any dependent objects
# necessary to make the object functional in the new instance
# (e.g. for a pipeline instance, arv-copy copies the pipeline
# template, input collection, docker images, git repositories). If
# --no-recursive is given, arv-copy copies only the single record
# identified by object-uuid.
#
# The user must have files $HOME/.config/arvados/{src}.conf and
# $HOME/.config/arvados/{dst}.conf with valid login credentials for
# instances src and dst.  If either of these files is not found,
# arv-copy will issue an error.

import argparse
import os
import sets
import sys
import logging

import arvados
import arvados.config
import arvados.keep

def main():
    logger = logging.getLogger('arvados.arv-copy')

    parser = argparse.ArgumentParser(
        description='Copy a pipeline instance from one Arvados instance to another.')

    parser.add_argument('--recursive', dest='recursive', action='store_true')
    parser.add_argument('--no-recursive', dest='recursive', action='store_false')
    parser.add_argument('object_uuid')
    parser.add_argument('source_arvados')
    parser.add_argument('destination_arvados')
    parser.set_defaults(recursive=True)

    args = parser.parse_args()

    # Create API clients for the source and destination instances
    src_arv = api_for_instance(args.source_arvados)
    dst_arv = api_for_instance(args.destination_arvados)

    # Identify the kind of object we have been given, and begin copying.
    t = uuid_type(args.object_uuid)
    if t == 'collection':
        result = copy_collection(args.object_uuid, src=src_arv, dst=dst_arv)
    elif t == 'pipeline_instance':
        result = copy_pipeline_instance(args.object_uuid, src=src_arv, dst=dst_arv)
    elif t == 'pipeline_template':
        result = copy_pipeline_template(args.object_uuid, src=src_arv, dst=dst_arv)
    else:
        abort("cannot copy object {} of type {}".format(args.object_uuid, t))

    print result
    exit(0)

# Creates an API client for the Arvados instance identified by
# instance_name.  Looks in $HOME/.config/arvados/instance_name.conf
# for credentials.
#
def api_for_instance(instance_name):
    if '/' in instance_name:
        abort('illegal instance name {}'.format(instance_name))
    config_file = os.path.join(os.environ['HOME'], '.config', 'arvados', "{}.conf".format(instance_name))
    cfg = arvados.config.load(config_file)

    if 'ARVADOS_API_HOST' in cfg and 'ARVADOS_API_TOKEN' in cfg:
        api_is_insecure = (
            cfg.get('ARVADOS_API_HOST_INSECURE', '').lower() in set(
                ['1', 't', 'true', 'y', 'yes']))
        client = arvados.api('v1',
                             host=cfg['ARVADOS_API_HOST'],
                             token=cfg['ARVADOS_API_TOKEN'],
                             insecure=api_is_insecure,
                             cache=False)
    else:
        abort('need ARVADOS_API_HOST and ARVADOS_API_TOKEN for {}'.format(instance_name))
    return client

def copy_collection(obj_uuid, src=None, dst=None):
    # Fetch the collection's manifest.
    c = src.collections().get(uuid=obj_uuid).execute()
    manifest = c['manifest_text']

    # Enumerate the block locators found in the manifest.
    collection_blocks = sets.Set()
    src_keep = arvados.keep.KeepClient(src)
    for line in manifest.splitlines():
        try:
            block_hash = line.split()[1]
            collection_blocks.add(block_hash)
        except ValueError:
            abort('bad manifest line in collection {}: {}'.format(obj_uuid, f))

    # Copy each block from src_keep to dst_keep.
    for locator in collection_blocks:
        data = src_keep.get(locator)
        logger.info("Retrieved %d bytes", len(data))
        dst_keep.put(data)

    # Copy the manifest and save the collection.
    dst_keep.put(manifest)
    return dst_keep.collections().create(manifest_text=manifest).execute()

def copy_pipeline_instance(obj_uuid, src=None, dst=None):
    raise NotImplementedError

def copy_pipeline_template(obj_uuid, src=None, dst=None):
    # fetch the pipeline template from the source instance
    old_pt = src.pipeline_templates().get(uuid=obj_uuid).execute()
    old_pt['name'] = old_pt['name'] + ' copy'
    del old_pt['uuid']
    del old_pt['owner_uuid']
    return dst.pipeline_templates().create(body=old_pt).execute()

uuid_type_map = {
    "4zz18": "collection",
    "d1hrv": "pipeline_instance",
    "p5p6p": "pipeline_template",
}

def uuid_type(object_uuid):
    type_str = object_uuid.split('-')[1]
    return uuid_type_map.get(type_str, None)

def abort(msg, code=1):
    print >>sys.stderr, "arv-copy:", msg
    exit(code)

if __name__ == '__main__':
    main()
