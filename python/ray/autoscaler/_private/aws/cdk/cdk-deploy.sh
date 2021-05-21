#!/usr/bin/env bash

# Cause the script to exit if a single command fails.
set -e

declare -a SUPPORTED_PYENV_VERSIONS=("3.6" "3.7" "3.8")

usage() {
    echo "usage: cdk-deploy -s stack-prefix [-a ami-id] [-p pyenv-version]"
}

while [[ $# -gt 0 ]]
do
    opt="$1"
    shift
    current_arg="$1"
    if [[ "$current_arg" =~ ^-{1,2}.* ]]; then
        usage >&2
    fi
    case "$opt" in
        -s|--stack-prefix) prefix="$1"; shift ;;
        -a|--ami-id) amiid="$1"; shift ;;
        -p|--pyenv-version) pyenvversion="$1"; shift ;;
        *            ) echo "ERROR: Invalid option: \" $opt \"" >&2
                       exit 1 ;;
    esac
done

if [ -z "$prefix" ]; then
    usage >&2
    echo "Please specify a prefix to setup AWS resources (e.g.: demo). " >&2
    exit 1
else
    echo "stack-prefix identified: $prefix"
    export CDK_PREFIX=$prefix
fi

if [ "$amiid" ]; then
    echo "Using user defined EC2 AMI: ${amiid}"
    export AMI=$amiid
else
    echo "Using default AMI."
fi
echo "For more regional AMIs, check https://github.com/amzn/amazon-ray#images"

if [ "$pyenvversion" ]; then
    if [[ ! "${SUPPORTED_PYENV_VERSIONS[*]}" =~ ${pyenvversion[*]} ]]; then
        echo "error: pyenv ${pyenvversion} not supported. Chose from: ${SUPPORTED_PYENV_VERSIONS[*]}"
        exit 1
    else
        export PYENV_VERSION_RAY=$pyenvversion
    fi
else
    echo "Using default pyenv version"
fi

cdk deploy
exit $?
