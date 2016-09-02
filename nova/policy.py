# Copyright (c) 2011 OpenStack Foundation
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

"""Policy Engine For Nova."""
import copy
import re
import sys

from oslo_config import cfg
from oslo_log import log as logging
from oslo_policy import policy
from oslo_utils import excutils
import six

from nova import exception
from nova.i18n import _LE, _LW
from nova import policies


CONF = cfg.CONF
LOG = logging.getLogger(__name__)
_ENFORCER = None
# This list is about the resources which support user based policy enforcement.
# Avoid sending deprecation warning for those resources.
USER_BASED_RESOURCES = ['os-keypairs']
# oslo_policy will read the policy configuration file again when the file
# is changed in runtime so the old policy rules will be saved to
# saved_file_rules and used to compare with new rules to determine the
# rules whether were updated.
saved_file_rules = []
KEY_EXPR = re.compile(r'%\((\w+)\)s')


def reset():
    global _ENFORCER
    if _ENFORCER:
        _ENFORCER.clear()
        _ENFORCER = None


def init(policy_file=None, rules=None, default_rule=None, use_conf=True):
    """Init an Enforcer class.

       :param policy_file: Custom policy file to use, if none is specified,
                           `CONF.policy_file` will be used.
       :param rules: Default dictionary / Rules to use. It will be
                     considered just in the first instantiation.
       :param default_rule: Default rule to use, CONF.default_rule will
                            be used if none is specified.
       :param use_conf: Whether to load rules from config file.
    """

    global _ENFORCER
    global saved_file_rules

    if not _ENFORCER:
        _ENFORCER = policy.Enforcer(CONF,
                                    policy_file=policy_file,
                                    rules=rules,
                                    default_rule=default_rule,
                                    use_conf=use_conf)
        register_rules(_ENFORCER)
        _ENFORCER.load_rules()

    # Only the rules which are loaded from file may be changed.
    current_file_rules = _ENFORCER.file_rules
    current_file_rules = _serialize_rules(current_file_rules)

    # Checks whether the rules are updated in the runtime
    if saved_file_rules != current_file_rules:
        _warning_for_deprecated_user_based_rules(current_file_rules)
        saved_file_rules = copy.deepcopy(current_file_rules)


def _serialize_rules(rules):
    """Serialize all the Rule object as string which is used to compare the
    rules list.
    """
    result = [(rule_name, str(rule))
              for rule_name, rule in six.iteritems(rules)]
    return sorted(result, key=lambda rule: rule[0])


def _warning_for_deprecated_user_based_rules(rules):
    """Warning user based policy enforcement used in the rule but the rule
    doesn't support it.
    """
    for rule in rules:
        # We will skip the warning for the resources which support user based
        # policy enforcement.
        if [resource for resource in USER_BASED_RESOURCES
                if resource in rule[0]]:
            continue
        if 'user_id' in KEY_EXPR.findall(rule[1]):
            LOG.warning(_LW("The user_id attribute isn't supported in the "
                            "rule '%s'. All the user_id based policy "
                            "enforcement will be removed in the "
                            "future."), rule[0])


def set_rules(rules, overwrite=True, use_conf=False):
    """Set rules based on the provided dict of rules.

       :param rules: New rules to use. It should be an instance of dict.
       :param overwrite: Whether to overwrite current rules or update them
                         with the new rules.
       :param use_conf: Whether to reload rules from config file.
    """

    init(use_conf=False)
    _ENFORCER.set_rules(rules, overwrite, use_conf)


def authorize(context, action, target, do_raise=True, exc=None):
    """Verifies that the action is valid on the target in this context.

       :param context: nova context
       :param action: string representing the action to be checked
           this should be colon separated for clarity.
           i.e. ``compute:create_instance``,
           ``compute:attach_volume``,
           ``volume:attach_volume``
       :param target: dictionary representing the object of the action
           for object creation this should be a dictionary representing the
           location of the object e.g. ``{'project_id': context.project_id}``
       :param do_raise: if True (the default), raises PolicyNotAuthorized;
           if False, returns False
       :param exc: Class of the exception to raise if the check fails.
                   Any remaining arguments passed to :meth:`authorize` (both
                   positional and keyword arguments) will be passed to
                   the exception class. If not specified,
                   :class:`PolicyNotAuthorized` will be used.

       :raises nova.exception.PolicyNotAuthorized: if verification fails
           and do_raise is True. Or if 'exc' is specified it will raise an
           exception of that type.

       :return: returns a non-False value (not necessarily "True") if
           authorized, and the exact value False if not authorized and
           do_raise is False.
    """
    init()
    credentials = context.to_dict()
    if not exc:
        exc = exception.PolicyNotAuthorized
    try:
        result = _ENFORCER.authorize(action, target, credentials,
                                     do_raise=do_raise, exc=exc, action=action)
    except policy.PolicyNotRegistered:
        with excutils.save_and_reraise_exception():
            LOG.exception(_LE('Policy not registered'))
    except Exception:
        credentials.pop('auth_token', None)
        with excutils.save_and_reraise_exception():
            LOG.debug('Policy check for %(action)s failed with credentials '
                      '%(credentials)s',
                      {'action': action, 'credentials': credentials})
    return result


def check_is_admin(context):
    """Whether or not roles contains 'admin' role according to policy setting.

    """

    init()
    # the target is user-self
    credentials = context.to_dict()
    target = credentials
    return _ENFORCER.authorize('context_is_admin', target, credentials)


@policy.register('is_admin')
class IsAdminCheck(policy.Check):
    """An explicit check for is_admin."""

    def __init__(self, kind, match):
        """Initialize the check."""

        self.expected = (match.lower() == 'true')

        super(IsAdminCheck, self).__init__(kind, str(self.expected))

    def __call__(self, target, creds, enforcer):
        """Determine whether is_admin matches the requested value."""

        return creds['is_admin'] == self.expected


def get_rules():
    if _ENFORCER:
        return _ENFORCER.rules


def register_rules(enforcer):
    enforcer.register_defaults(policies.list_rules())


def get_enforcer():
    # This method is for use by oslopolicy CLI scripts. Those scripts need the
    # 'output-file' and 'namespace' options, but having those in sys.argv means
    # loading the Nova config options will fail as those are not expected to
    # be present. So we pass in an arg list with those stripped out.
    conf_args = []
    # Start at 1 because cfg.CONF expects the equivalent of sys.argv[1:]
    i = 1
    while i < len(sys.argv):
        if sys.argv[i].strip('-') in ['namespace', 'output-file']:
            i += 2
            continue
        conf_args.append(sys.argv[i])
        i += 1

    cfg.CONF(conf_args, project='nova')
    init()
    return _ENFORCER
