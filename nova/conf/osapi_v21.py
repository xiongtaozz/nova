# Copyright 2015 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg

api_opts_group = cfg.OptGroup(name="osapi_v21", title="API v2.1 Options")

api_opts = [
    cfg.ListOpt("extensions_blacklist",
        default=[],
        deprecated_for_removal=True,
        deprecated_since="12.0.0",
        deprecated_reason="""
API extensions are now part of the standard API. API extensions should be
disabled using policy, rather than via these configuration options.""",
        help="""
This option is a list of all of the v2.1 API extensions to never load.

Possible values:

* A list of strings, each being the alias of an extension that you do not
  wish to load.

Related options:

* enabled
* extensions_whitelist
"""),
    cfg.ListOpt("extensions_whitelist",
        default=[],
        deprecated_for_removal=True,
        deprecated_since="12.0.0",
        deprecated_reason="""
API extensions are now part of the standard API. API extensions should be
disabled using policy, rather than via these configuration options.""",
        help="""
This is a list of extensions. If it is empty, then *all* extensions except
those specified in the extensions_blacklist option will be loaded. If it is not
empty, then only those extensions in this list will be loaded, provided that
they are also not in the extensions_blacklist option.

Possible values:

* A list of strings, each being the alias of an extension that you wish to
  load, or an empty list, which indicates that all extensions are to be run.

Related options:

* enabled
* extensions_blacklist
"""),
    cfg.StrOpt("project_id_regex",
        deprecated_for_removal=True,
        deprecated_since="13.0.0",
        deprecated_reason="""
Recent versions of nova constrain project IDs to hexadecimal characters and
dashes. If your installation uses IDs outside of this range, you should use
this option to provide your own regex and give you time to migrate offending
projects to valid IDs before the next release.""",
        help="""
This option is a string representing a regular expression (regex) that matches
the project_id as contained in URLs. If not set, it will match normal UUIDs
created by keystone.

Possible values:

* A string representing any legal regular expression
"""),
]


def register_opts(conf):
    conf.register_group(api_opts_group)
    conf.register_opts(api_opts, api_opts_group)


def list_opts():
    return {api_opts_group: api_opts}
