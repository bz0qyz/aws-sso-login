#!/usr/bin/env python3
import sys
import os
import signal
import shutil
import logging
import argparse
import subprocess
from configparser import ConfigParser
from lib.ui import QApp, MainWindow

# Global variables
APP = {
    'name': 'aws-sso-login',
    'description': 'AWS SSO Login Manager',
    'version': '1.1.0',
    'author': 'Russ Cook <bz0qyz@protonmail.com>',
}
DEFAULTS = {
    "config": {
        "aws": f"{os.path.expanduser('~')}/.aws/config",
        "eks": f"{os.path.expanduser('~')}/.eks_auth",
        "kube": f"{os.path.expanduser('~')}/.kube/config",
    },
    "cmd": {
        "aws": f"{shutil.which('aws')}",
        "kubectl": f"{shutil.which('kubectl')}",
        "docker": f"{shutil.which('docker')}"
    }
}


# Application Arguments parser
class EnvDefault(argparse.Action):
    """ Argparse Action that uses ENV Vars for default values """
    def __init__(self, envvar, required=False, default=None, **kwargs):
        if envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
                required = False

        super().__init__(default=default,
                        required=required,
                        **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

ARGUMENTS = {
    "config": {
        "config_awscli": {"label": "aws config", "help": "Path to 'aws' config file."},
        "config_eks": {"label": "eks config", "help": "Path to 'eks_auth' config file."}
    },
    "cmd": {
        "cmd_awscli": {"label": "aws binary", "help": "Path to 'aws' binary."},
        "cmd_docker": {"label": "docker binary", "help": "Path to 'docker' binary."},
        "cmd_kubectl": {"label": "kubectl binary", "help": "Path to 'kubectl' binary."}
    },
    "options": {
        "skip_login": {"label": "AWS SSO Login", "help": "Skip login to AWS SSO.", "invert": True, "enabled": True},
        "skip_eks": {"label": "AWS EKS Auth", "help": "Skip EKS authorization.", "invert": True, "enabled": True},
        "do_ecr": {"label": "AWS ECR Auth", "help": "Login to AWS ECR. (requires docker)", "invert": False, "enabled": True}
    }
}

parser = argparse.ArgumentParser(
    description=f"{APP['description']} v{APP['version']}",
    epilog="NOTE: You cannot run this command in Windows Subsystem for Linux (WSL) as it launches a web browser for login to AWS."
)
parser.add_argument('-v','--verbose', action="count", default=False, help='Show verbose output.')
parser.add_argument('--config-eks', help=f"{ARGUMENTS['config']['config_eks']['help']}",
    metavar=DEFAULTS['config']['eks'], default=DEFAULTS['config']['eks'],
    action=EnvDefault, envvar="CONFIG_EKS"
)
parser.add_argument('--cmd-awscli', help=f"{ARGUMENTS['cmd']['cmd_awscli']['help']}",
    metavar=DEFAULTS['cmd']['aws'], default=DEFAULTS['cmd']['aws'],
    action=EnvDefault, envvar="CMD_AWSCLI"
)
parser.add_argument('--config-awscli', help=f"{ARGUMENTS['config']['config_awscli']['help']}",
    metavar=DEFAULTS['config']['aws'], default=DEFAULTS['config']['aws'],
    action=EnvDefault, envvar="CONFIG_AWSCLI"
)
parser.add_argument('--cmd-kubectl', help=f"{ARGUMENTS['cmd']['cmd_kubectl']['help']}",
    metavar=DEFAULTS['cmd']['kubectl'], default=DEFAULTS['cmd']['kubectl'],
    action=EnvDefault, envvar="CMD_KUBECTL"
)
parser.add_argument('--cmd-docker', help=f"{ARGUMENTS['cmd']['cmd_docker']['help']}",
    metavar=DEFAULTS['cmd']['docker'], default=DEFAULTS['cmd']['docker'],
    action=EnvDefault, envvar="CMD_DOCKER"
)
parser.add_argument('--skip-login', action="store_true", help=f"{ARGUMENTS['options']['skip_login']['help']}")
parser.add_argument('--skip-eks', action="store_true", help=f"{ARGUMENTS['options']['skip_eks']['help']} (requires kubectl)")
parser.add_argument('--do-ecr', action="store_true", help=f"{ARGUMENTS['options']['do_ecr']['help']}")
parser.add_argument('--dry-run', action="store_true", help='Dry Run. Show, but no not execute any commands.')
parser.add_argument('-q','--no-ui', action="store_true", help='Do not show the UI interface.')
args = parser.parse_args()

# Application Logging
log = logging.getLogger()
# remove all default handlers
for handler in log.handlers:
    log.removeHandler(handler)
console = logging.StreamHandler()
console_format = logging.Formatter(
    f'%(asctime)s %(levelname)-8s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console.setFormatter(console_format)
log.addHandler(console)
DRYRUN = 60
logging.addLevelName(DRYRUN, "DRYRUN")
logging.__all__ += ["DRYRUN"]
log.setLevel(logging.INFO)
if args.verbose:
    log.setLevel(logging.DEBUG)


class AwsProfile():
    def __init__(self, aws_config, section):
        self.config_attrs = ('region', 'sso_region', 'source_profile', 'role_arn', 'sso_account_id', 'sso_role_name', 'sso_start_url')
        self.section = section

        self.name = section[8:] if section.startswith('profile ') else section
        # Load the aws config attributes
        for attr in self.config_attrs:
            setattr(self, attr, self.__get_config_attribute__(aws_config, attr))

    def __get_config_attribute__(self, aws_config, attr: str):
        """ Get the value of an attribute from the aws config file """
        try:
            return aws_config.get(self.section, attr)
        except Exception:
            return None

class KubeConfig():
    def __init__(self, eks_config, section):
        self.config_attrs = ('ENABLE', 'AWS_REGION', 'EKS_CLUSTER', 'AWS_PROFILE', 'ROLE', 'KUBE_CONFIG')
        self.context = section
        self.aws_profile = None
        self.enable = False
        self.kube_config = DEFAULTS['config']['kube']
        # Load the aws config attributes
        for attr in self.config_attrs:
            value = self.__get_config_attribute__(eks_config, attr)
            if value:
                setattr(self, attr.lower(), value)

        if hasattr(self, "enable"):
            self.enable = self.__str_to_bool__(self.enable)
        else:
            self.enable = True

    def __get_config_attribute__(self, eks_config, attr: str):
        """ Get the value of an attribute from the eks_auth config file """
        try:
            return eks_config.get(self.context, attr).lower()
        except Exception:
            return None

    def __str_to_bool__(self, str):
        if not str:
            return False
        if str.lower() in ['1', 'true']:
            return True
        else:
            return False
        


def __init_eks_auth__():
    """ Initialize the EKS config file """
    if os.path.isfile(args.config_eks):
        return True
    else:
        log.info("EKS Config file not found. Creating...")
        try:
            with open(args.config_eks, 'w') as f:
                f.write(f"""
[DEFAULT]
## Configuration file for eks_auth function ##
## Example:
#[KUBE_CONTEXT]
#ENABLE=true
#EKS_CLUSTER=my-cluster
#AWS_PROFILE=default
#AWS_REGION=us-east-1
#ROLE=kubernetes-admins-access
""")
            return True
        except Exception as e:
            log.error("Error creating EKS config file: {}".format(e))
            return False

def __retval_to_bool(int):
    """ Convert the return value of a subprocess to a boolean """
    if int == 0:
        return True
    else:
        return False

def __do_subprocess_popen(title, cmd=[], dryreturn=""):
    """ Run a subprocess and return the output """
    if not isinstance(cmd, list):
        cmd = [cmd]
    log.debug(f"Running subprocess command: {' '.join(cmd)}")
    if args.dry_run:
        log.log(DRYRUN, f"Command: {' '.join(cmd)}")
        return dryreturn
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if err:
            log.error(f"Error running command: {title} - {err.decode('utf-8')}")
            return False
        else:
            return out.decode('utf-8')
    except KeyboardInterrupt:
        log.error("%s canceled by user.", title)
        return False

def __do_subprocess_call(title, cmd=[]):
    """ Run a subprocess and return the return code """
    if not isinstance(cmd, list):
        cmd = [cmd]
    log.debug(f"Running subprocess command: {' '.join(cmd)}")
    if args.dry_run:
        log.log(DRYRUN, f"Command: {' '.join(cmd)}")
        return True
    try:
        retval = subprocess.call(cmd)
    except KeyboardInterrupt:
        log.error("%s canceled by user.", title)
        return False
    return __retval_to_bool(retval)

def aws_sso_login(profile):
    """ Login to AWS SSO """
    log.info("Logging into AWS SSO for profile: %s", profile.name)
    cmd = [args.cmd_awscli, "--profile", f"{profile.name}", "sso", "login"]
    return __do_subprocess_call("AWS SSO Login", cmd)
    

def aws_ecr_docker_login(profile):
    """ Login to AWS ECR """
    log.info("Authorizing docker login to AWS ECR for profile: %s", profile.name)
    cmd = [
            args.cmd_awscli, 
            "--profile", f"{profile.name}",
            "ecr", "get-login-password",
            "--region", f"{profile.region}"
        ]
    ecr_password =  __do_subprocess_popen("AWS ECR Authorization", cmd, "password-from_get-login-password")
    if ecr_password:
        cmd = [
                args.cmd_docker, "login",
                "--username", "AWS",
                "--password", f"{ecr_password}", 
                f"{profile.sso_account_id}.dkr.ecr.{profile.region}.amazonaws.com"
            ]
        return __do_subprocess_call("Docker ECR Authorization", cmd)
    else:
        return False

def aws_eks_kubectl_login(kubeconfig):
    """ Login to AWS EKS and autornize kubectl """
    log.info("Authorizing kubectl to AWS EKS for cluster: %s. Using kube context: %s", kubeconfig.eks_cluster, kubeconfig.context)

    # Set the AWS region variable
    if hasattr(kubeconfig, "aws_region"):
        region = kubeconfig.aws_region
    else:
        region = kubeconfig.aws_profile.region

    cmd = [
            args.cmd_awscli,
            "--profile", f"{kubeconfig.aws_profile.name}",
            "eks", "update-kubeconfig",
            "--name", f"{kubeconfig.eks_cluster}",
            "--region", f"{region}",
            "--alias", f"{kubeconfig.context}",
            "--output", "json"
        ]
    # Add a role if specified
    if hasattr(kubeconfig, "role"):
        cmd.extend(["--role-arn", f"arn:aws:iam::{kubeconfig.aws_profile.sso_account_id}:role/{kubeconfig.eks_cluster}-{kubeconfig.role}"])
    # Add a specific kube config file if specified
    if hasattr(kubeconfig, "kube_config"):
        cmd.extend(["--kubeconfig", f"{kubeconfig.kube_config}"])

    output = __do_subprocess_popen("AWS EKS Kubectl Authorization", cmd, None)
    if output:
        log.info(output.rstrip())
    return True

def signal_handler(signal, frame):
	log.info('Canceling login process.')
	sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    log.debug("Starting aws-login-manager")
    if args.dry_run:
        log.log(DRYRUN, "Dry run mode enabled. No changes will be made.")
    PROFILES = {}
    KUBES = {}
    OPS_ENABLED = {
        "kubectl": (not args.skip_eks),
        "docker": args.do_ecr
    }

    if not os.path.isfile(args.cmd_kubectl):
        OPS_ENABLED["kubectl"] = False
        ARGUMENTS["options"]["skip_eks"]["enabled"] = False
        log.warning(f"Kubectl command file: {args.cmd_kubectl}, not found. Kubectl login will be disabled.")
    if not os.path.isfile(args.cmd_docker):
        OPS_ENABLED["docker"] = False
        ARGUMENTS["options"]["do_ecr"]["enabled"] = False
        log.warning(f"Docker command file: {args.cmd_docker}, not found. Docker ECR login will be disabled.")

    # Verify that shell commands are installed 
    # AWS CLI is required for sso login, so exit if it's not found
    if not os.path.isfile(args.cmd_awscli):
        log.error(f"AWS CLI command file: {args.cmd_awscli}, not found. Unable to continue.")
        log.info("Use the argument --cmd-awscli to specify the path to the aws binary.")
        sys.exit(1)
    if not os.path.isfile(args.config_awscli):
        log.error(f"AWS config file: {args.config_awscli}, not found. Unable to continue.")
        sys.exit(1)
    if not __init_eks_auth__():
        sys.exit(1)

    # Create parsers for the configuration files
    aws_config = ConfigParser()
    aws_config.read(os.path.expanduser(args.config_awscli))
    eks_config = ConfigParser()
    eks_config.read(os.path.expanduser(args.config_eks))

    # Create a dictionary of profiles
    log.debug("Loading AWS Config profiles from: %s", args.config_awscli)
    for section in aws_config.sections():
        profile = AwsProfile(aws_config, section)
        PROFILES[profile.name] = profile
    
    # Create a dictionary of EKS clusters
    log.debug("Loading EKS Configuration from: %s", args.config_eks)
    for section in eks_config.sections():
        kube_config = KubeConfig(eks_config, section)
        KUBES[kube_config.context] = kube_config
    
    # Add the AWS Profile to the EKS cluster Config
    for name, kubeconfig in KUBES.items():
        if kubeconfig.aws_profile:
            kubeconfig.aws_profile = PROFILES[kubeconfig.aws_profile]

    # Print out the profiles
    if args.verbose >= 2 :
        print(" ******** [AWS PROFILES] ******** ")
        for name, profile in PROFILES.items():
            print("[{}]".format(name))
            for attr in profile.__dict__.keys():
                value = getattr(profile, attr)
                if value and isinstance(value, str):
                    print("{}: {}".format(attr, value))
            print()

    # Print out the EKS clusters
    if args.verbose >= 2 :
        print(" ******** [EKS Clusters] ******** ")
        for name, kubeconfig in KUBES.items():
            print("[{}]".format(name))
            for attr in kubeconfig.__dict__.keys():
                value = getattr(kubeconfig, attr)
                if isinstance(value, AwsProfile):
                    print(f"[aws profile: {value.name}]")
                    for pattr in value.__dict__.keys():
                        pvalue = getattr(value, pattr)
                        if pvalue and isinstance(pvalue, str):
                            print("  {}: {}".format(pattr, pvalue))
                elif isinstance(value, str):
                    print("{}: {}".format(attr, value))
            print()
    
    if not args.no_ui:
        ui_args = {
            "app": APP,
            "ops_enabled": OPS_ENABLED,
            "aws_profiles": PROFILES,
            "eks_clusters": KUBES,
            "options": args,
            "arguments": ARGUMENTS
        }
        app = QApp
        window = MainWindow(**ui_args)
        window.show()
        app.exec()

        if window.canceled:
            log.info("Login process canceled by user.")
            sys.exit(1)

    
    for name, profile in PROFILES.items():
        
        if hasattr(profile, "sso_start_url") and profile.sso_start_url:
            # Login to AWS SSO
            if not args.skip_login:
                try:
                    if aws_sso_login(profile):
                        log.info("AWS SSO Login successful for profile: %s", profile.name)
                    else:
                        log.error("AWS SSO Login failed for profile: %s", profile.name)
                except KeyboardInterrupt:
                    log.error("AWS SSO Login canceled by user.")
                    break

            # Login to AWS ECR
            if args.do_ecr and OPS_ENABLED["docker"]:
                try:
                    if aws_ecr_docker_login(profile):
                        log.info("AWS ECR Login successful for profile: %s", profile.name)
                    else:
                        log.error("AWS ECR Login failed for profile: %s", profile.name)
                except KeyboardInterrupt:
                    log.error("AWS ECR Login canceled by user.")
                    break

    if not args.skip_eks and OPS_ENABLED["kubectl"]:
        for name, kubeconfig in KUBES.items():
            if kubeconfig.aws_profile and kubeconfig.enable:
                try:
                    if not aws_eks_kubectl_login(kubeconfig):
                        log.error("AWS EKS Login failed for Cluster: %s", kubeconfig.eks_cluster)
                except KeyboardInterrupt:
                    log.error("AWS EKS Login canceled by user.")
                    break

sys.exit(0)