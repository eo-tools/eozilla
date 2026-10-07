#!/usr/bin/env bash
# Copy individual recipes. Running this file does not execute any commands below.
exit 0

# --8<-- [start:server]
pixi run serve
# --8<-- [end:server]

# --8<-- [start:configure]
cuiman configure --api-url http://127.0.0.1:8008 --auth-type none
# --8<-- [end:configure]

# --8<-- [start:inspect]
cuiman --help
cuiman list-processes
cuiman get-process primes_between
# --8<-- [end:inspect]

# --8<-- [start:template]
cuiman create-request primes_between --format json
# --8<-- [end:template]

# --8<-- [start:validate]
cuiman validate-request primes_between -i min_val=10 -i max_val=80
# --8<-- [end:validate]

# --8<-- [start:submit]
cuiman execute-process primes_between -i min_val=10 -i max_val=80
# --8<-- [end:submit]

# --8<-- [start:jobs]
cuiman list-jobs
cuiman get-job YOUR_JOB_ID
# --8<-- [end:jobs]

# --8<-- [start:results]
cuiman get-job-results YOUR_JOB_ID
# --8<-- [end:results]

# --8<-- [start:failure]
cuiman execute-process sleep_a_while -i duration=2 -i fail=true
# --8<-- [end:failure]

# --8<-- [start:dismiss]
cuiman dismiss-job YOUR_JOB_ID
# --8<-- [end:dismiss]

# --8<-- [start:scene-validate]
cuiman validate-request simulate_scene --request examples/guides/cuiman/simulate-scene-request.json
# --8<-- [end:scene-validate]

# --8<-- [start:scene-submit]
cuiman execute-process simulate_scene --request examples/guides/cuiman/simulate-scene-request.json
# --8<-- [end:scene-submit]

# --8<-- [start:app]
cuiman show-app
# --8<-- [end:app]

# --8<-- [start:python-api]
python -m examples.guides.cuiman.api
# --8<-- [end:python-api]

# --8<-- [start:python-app]
python -m examples.guides.cuiman.app
# --8<-- [end:python-app]

# --8<-- [start:python-openers]
python -m examples.guides.cuiman.openers
# --8<-- [end:python-openers]
