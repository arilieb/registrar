#!/bin/bash

set -e
# To run this script you need to run the following command in a separate terminals:
#   > kli witness demo

# EMN3HVTrF7Vs68L_xewuc2m33VH-N-rQnNtwuWu8JXjR
kli init --name external --salt 0ACDEyMzQ1Njc4OWxtbm9GhI --nopasscode --config-dir "${REGISTRAR_SCRIPT_DIR}" --config-file registrar-config
kli incept --name external --alias external --file "${REGISTRAR_SCRIPT_DIR}/data/base-aid.json"

kli init --name qvi --salt 0ACDEyMzQ1Njc4OWxtbm9qvi --nopasscode --config-dir "${REGISTRAR_SCRIPT_DIR}" --config-file registrar-config
kli incept --name qvi --alias qvi --file "${REGISTRAR_SCRIPT_DIR}"/data/base-aid.json

kli init --name registrar --salt 0ACDEyMzQ1Njc4OWxtbm9reg --config-dir "${REGISTRAR_SCRIPT_DIR}" --config-file registrar-config --nopasscode
kli incept --name registrar --alias registrar --icount 1 --isith "1" --ncount 1 --nsith "1" --toad 0 --config "${REGISTRAR_SCRIPT_DIR}"
kli export --name registrar --alias registrar --ends > /tmp/registrar.cesr

echo 'resolving external'
kli oobi resolve --name qvi --oobi-alias external --oobi http://127.0.0.1:5642/oobi/EMN3HVTrF7Vs68L_xewuc2m33VH-N-rQnNtwuWu8JXjR/witness/BBilc4-L3tFUnfM_wJr4S4OJanAv_VmF_dJNN6vkf2Ha
echo 'resolving qvi'
kli oobi resolve --name external --oobi-alias qvi --oobi http://127.0.0.1:5642/oobi/EAQa8uKZq_PMLLTQOyTGbQoYgWc8GFzKqu67PTJO1u0u/witness/BBilc4-L3tFUnfM_wJr4S4OJanAv_VmF_dJNN6vkf2Ha
kli oobi resolve --name registrar --oobi-alias qvi --oobi http://127.0.0.1:5642/oobi/EAQa8uKZq_PMLLTQOyTGbQoYgWc8GFzKqu67PTJO1u0u/witness/BBilc4-L3tFUnfM_wJr4S4OJanAv_VmF_dJNN6vkf2Ha
echo 'resolving registrar'
kli import --name external --alias registrar --file /tmp/registrar.cesr

kli vc registry incept --name external --alias external --registry-name vLEI-external
kli vc registry incept --name qvi --alias qvi --registry-name vLEI-qvi

# Issue QVI credential vLEI from GLEIF External to QVI
kli vc create --name external --alias external --registry-name vLEI-external --schema EBfdlu8R27Fbx-ehrqwImnK-8Cm79sqbAQ4MmvEAYqao --recipient EAQa8uKZq_PMLLTQOyTGbQoYgWc8GFzKqu67PTJO1u0u --data @"${REGISTRAR_SCRIPT_DIR}/data/qvi-data.json"
SAID=$(kli vc list --name external --alias external --issued --said --schema EBfdlu8R27Fbx-ehrqwImnK-8Cm79sqbAQ4MmvEAYqao)
kli ipex grant --name external --alias external --said "${SAID}" --recipient EAQa8uKZq_PMLLTQOyTGbQoYgWc8GFzKqu67PTJO1u0u
GRANT=$(kli ipex list --name qvi --alias qvi --poll --said)
kli ipex admit --name qvi --alias qvi --said "${GRANT}"
kli vc list --name qvi --alias qvi
