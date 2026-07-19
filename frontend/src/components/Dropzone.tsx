import { FileArchive, UploadCloud } from "lucide-react";
import { useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from "react";

interface DropzoneProps {
  file: File | null;
  onFile: (file: File) => void;
  disabled?: boolean;
}

const ACCEPTED = ".json,.jsonl,.csv,.parquet";

export function Dropzone({ file, onFile, disabled = false }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const choose = () => {
    if (!disabled) inputRef.current?.click();
  };

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0];
    if (next) onFile(next);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const next = event.dataTransfer.files[0];
    if (next) onFile(next);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose();
    }
  };

  return (
    <div
      className={`dropzone${dragging ? " is-dragging" : ""}${disabled ? " is-disabled" : ""}`}
      onClick={choose}
      onKeyDown={onKeyDown}
      onDragEnter={() => setDragging(true)}
      onDragLeave={() => setDragging(false)}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Choose a seed dataset file"
    >
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={ACCEPTED}
        onChange={onChange}
        disabled={disabled}
        data-testid="seed-file-input"
      />
      <span className="dropzone__icon" aria-hidden="true">
        {file ? <FileArchive size={23} /> : <UploadCloud size={23} />}
      </span>
      {file ? (
        <>
          <strong>{file.name}</strong>
          <span>{Math.max(1, Math.round(file.size / 1024)).toLocaleString()} KB · Ready to import</span>
        </>
      ) : (
        <>
          <strong>Drop a seed dataset here</strong>
          <span>or choose JSON, JSONL, CSV, or Parquet · up to 50,000 rows</span>
        </>
      )}
    </div>
  );
}
