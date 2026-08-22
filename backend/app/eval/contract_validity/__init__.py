"""W8 P6 Golden contract validity / Gate G (eval-only, no product semantics)."""

from app.eval.contract_validity.models import (
    AdversarialRetrievalOutcome,
    ContractValidityRecord,
    MeasurementLayer,
    MemoryCaseKind,
    MetricValidityEntry,
    PrimaryToolContractClass,
    ToolSecondaryTag,
    Validity,
)
from app.eval.contract_validity.adversarial import bge_capability_valid_proven_from_probe
from app.eval.contract_validity.runner import (
    BENCHMARK_SEMANTICS_SHA,
    VALIDATED_MERGED_MASTER_SHA,
    BgeProbeResult,
    build_contract_validity_report,
    gate_g_readiness,
    run_bge_retrieval_validity_probe,
)

__all__ = [
    "AdversarialRetrievalOutcome",
    "BENCHMARK_SEMANTICS_SHA",
    "BgeProbeResult",
    "ContractValidityRecord",
    "MeasurementLayer",
    "MemoryCaseKind",
    "MetricValidityEntry",
    "PrimaryToolContractClass",
    "ToolSecondaryTag",
    "VALIDATED_MERGED_MASTER_SHA",
    "Validity",
    "bge_capability_valid_proven_from_probe",
    "build_contract_validity_report",
    "gate_g_readiness",
    "run_bge_retrieval_validity_probe",
]
