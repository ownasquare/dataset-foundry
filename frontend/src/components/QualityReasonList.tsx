import type { CandidateReason } from "../api/types";
import { Disclosure } from "./Disclosure";
import { InfoTip } from "./InfoTip";
import {
  qualityReasonLabel,
  UNKNOWN_REASON_EVIDENCE,
} from "./qualityReasonPresentation";

export function QualityReasonList({
  reasons,
  rawCodes,
}: {
  reasons: CandidateReason[];
  rawCodes: string[];
}) {
  return (
    <div className="quality-reasons">
      <div className="quality-reasons__heading">
        <strong>Why this needs attention</strong>
        <InfoTip label="quality reasons">
          These labels summarize automated checks. Evidence shows what the scorer observed; the
          final decision remains yours.
        </InfoTip>
      </div>
      <ul className="quality-reasons__list">
        {reasons.map((reason, index) => (
          <li key={`${reason.code}-${index}`}>
            <strong>{qualityReasonLabel(reason.code)}</strong>
            <span>{reason.evidence?.trim() || UNKNOWN_REASON_EVIDENCE}</span>
          </li>
        ))}
      </ul>
      <Disclosure summary="Show raw reason codes">
        <div className="reason-codes" aria-label="Raw quality reason codes">
          {rawCodes.map((code, index) => <code key={`${code}-${index}`}>{code}</code>)}
        </div>
      </Disclosure>
    </div>
  );
}
