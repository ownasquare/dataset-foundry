const REASON_LABELS: Record<string, string> = {
  exact_duplicate: "Exact duplicate",
  near_duplicate: "Near duplicate",
  borderline_quality: "Close to quality threshold",
  below_quality_threshold: "Below quality threshold",
  insufficient_or_excessive_length: "Length outside useful range",
  unhelpful_instruction_response_overlap: "Weak instruction-response fit",
  low_lexical_richness: "Low lexical variety",
  boilerplate_detected: "Boilerplate detected",
  low_seed_novelty: "Too similar to a seed",
  low_pool_diversity: "Too similar to accepted examples",
  constraint_violation: "Recipe constraint not met",
  REFERENCE_DETAIL_EXPANDED: "Adds an unsupported detail",
  CONTRADICTS_REFERENCE: "Contradicts the source",
  UNSUPPORTED_CARE_INSTRUCTION: "Unsupported care guidance",
};

export const UNKNOWN_REASON_EVIDENCE =
  "This check came from a custom or newer scorer. Review the score details before deciding.";

export function humanizeIdentifier(value: string): string {
  const words = value
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replaceAll(/[_-]+/g, " ")
    .toLowerCase();
  return words ? words[0]!.toUpperCase() + words.slice(1) : "Quality signal";
}

export function qualityReasonLabel(code: string): string {
  return REASON_LABELS[code] ?? humanizeIdentifier(code);
}
