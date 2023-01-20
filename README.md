# AWS SSO Login Manager

## Description
The AWS Login manager simplifies session management for AWS SSO.

## Features
- Allows you to login to multiple AWS SSO accounts and roles with a single command.
- Optionally authorize docker with AWS credentials for each AWS profile using AWS SSO.
- Optionally Authorize kubeconfig for EKS with AWS credentials for each AWS profile using AWS SSO.


## Usage
```
aws-login-manager.py [-h] [-v] [--dry-run] \
  [--config-eks ${HOME}.eks_auth] \
  [--cmd-awscli /usr/local/bin/aws] \
  [--config-awscli ${HOME}/.aws/config] \
  [--cmd-kubectl /usr/local/bin/kubectl] \
  [--cmd-docker /usr/local/bin/docker] \
  [--skip-login] [--skip-eks] [--do-ecr] 
```

### Arguments
| Argument | ENV Variable| Description | Default Value |
| -------- |------------ | ----------- | ------------- |
| `-h, --help` | - | show this help message and exit | - |
| `-v, --verbose` | - | Enable verbose logging. Add multiple to increase verbosity. | - |
| `--dry-run` | - | Dry run mode. Displays commands that would have run | - |
| `--config-eks` | `CONFIG_EKS` | Path to EKS config file | `${HOME}/.eks_auth` |
| `--config-awscli` | `CONFIG_AWSCLI` | Path to awscli config file | `${HOME}/.aws/config` |
| `--cmd-awscli` | `CMD_AWSCLI` | Path to awscli | `$(which aws)` |
| `--cmd-kubectl` | `CMD_KUBECTL` | Path to kubectl | `$(which kubectl)` |
| `--cmd-docker` | `CMD_DOCKER` | Path to docker | `$(which docker)` |
| `--skip-login` | - | Skip login to AWS SSO | `False` |
| `--skip-eks` | - | Skip kubeclt EKS authorization | `False` |
| `--do-ecr` | - | Also login to AWS ECR. (requires local docker) | `False` |



The script will attempt to locate the following application in your path (each can be specified using command arguments):
- `aws`
- `docker`
- `kubectl`

If the application is not found in your path, that feature will be disabled. If `aws` is not found, the script will exit.

## Configuration
The script will attempt to locate the following configuration files in your path (each can be specified using command arguments):
- `${HOME}/.aws/config` (AWS CLI configuration)
- `${HOME}/.eks_auth` (EKS configuration - See **EKS Configuration** below)


### EKS Configuration
This script utilizes a configuration file to specify the EKS clusters and roles to authorize. The configuration file is `ini` format similar to the AWS CLI configuration file. 

Each section of the configuration file represents a cluster. The section name is the name of the kube context. The section contains the following keys:
 - `ENABLE`: (optional) If set to `0` or `false` the cluster will be skipped. Default is `true`.
 - `EKS_CLUSTER`: (required) The name of the EKS cluster.
 - `AWS_PROFILE`: (required) The name of the AWS profile to use for the cluster authentication.
 - `AWS_REGION`: (optional) The AWS region of the EKS cluster. If not specified the region will be determined from the AWS CLI configuration file.
 - `ROLE`: (optional) The name of the AWS role to assume for the cluster authentication. If not specified, no role will be used.
 - `KUBE_CONFIG`: (optional) The path to the kubeconfig file to update. If not specified, the default kubeconfig file will be used.

The following is an example cluster configuration section:
```
[prod-us]
ENABLE=true
EKS_CLUSTER=prod-eks-cluster-name
AWS_PROFILE=default
AWS_REGION=us-east-1
ROLE=kubernetes-admins-access
KUBE_CONFIG=~/.kube/config.prod
```
