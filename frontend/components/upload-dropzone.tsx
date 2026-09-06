// frontend/components/upload-dropzone.tsx
'use client';

import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { FileText, UploadCloud, X } from 'lucide-react';

interface UploadDropzoneProps {
    file: File | null;
    error: string | null;
    onFile: (file: File | null) => void;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.fountain'];

// Provide accessible drag-and-drop and conventional file-picker behavior.
export function UploadDropzone({ file, error, onFile }: UploadDropzoneProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [dragging, setDragging] = useState(false);

    // Forward the first selected file to the upload page's validation layer.
    function handleChange(event: ChangeEvent<HTMLInputElement>) {
        onFile(event.target.files?.[0] ?? null);
        event.target.value = '';
    }

    // Accept a dropped file and reset the highlighted drag state.
    function handleDrop(event: DragEvent<HTMLDivElement>) {
        event.preventDefault();
        setDragging(false);
        onFile(event.dataTransfer.files?.[0] ?? null);
    }

    return (
        <div>
            <div
                onDragEnter={() => setDragging(true)}
                onDragLeave={() => setDragging(false)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
                className={`rounded-xl border border-dashed px-6 py-10 text-center transition ${dragging ? 'border-violet-500 bg-violet-50' : error ? 'border-rose-300 bg-rose-50/40' : 'border-violet-300 bg-[#fbfeff] hover:border-violet-500'}`}
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept={ALLOWED_EXTENSIONS.join(',')}
                    onChange={handleChange}
                    className="sr-only"
                    aria-label="Choose screenplay file"
                />

                {file ? (
                    <div className="mx-auto flex max-w-md items-center gap-4 rounded-lg border border-[#c9e1ec] bg-[#f2f9fc] p-4 text-left">
                        <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-violet-100 text-violet-700">
                            <FileText size={22} aria-hidden="true" />
                        </span>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-semibold text-slate-900">{file.name}</p>
                            <p className="mt-1 text-xs text-slate-500">{formatBytes(file.size)}</p>
                        </div>
                        <button
                            type="button"
                            onClick={() => onFile(null)}
                            className="rounded-lg p-2 text-slate-400 hover:bg-white hover:text-slate-700"
                            aria-label="Remove selected file"
                        >
                            <X size={18} />
                        </button>
                    </div>
                ) : (
                    <>
                        <span className="mx-auto grid size-12 place-items-center rounded-xl bg-violet-100 text-violet-700">
                            <UploadCloud size={25} strokeWidth={1.8} aria-hidden="true" />
                        </span>
                        <p className="mt-4 text-sm font-semibold text-slate-900">Drop your screenplay here</p>
                        <p className="mt-1.5 text-xs text-slate-500">Supports PDF, TXT, and Fountain (.fountain)</p>
                        <button
                            type="button"
                            onClick={() => inputRef.current?.click()}
                            className="mt-5 rounded-lg bg-violet-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-800"
                        >
                            Choose File
                        </button>
                    </>
                )}
            </div>
            {error && <p className="mt-3 text-sm font-medium text-rose-600" role="alert">{error}</p>}
        </div>
    );
}

// Display file sizes in familiar screenplay-upload units.
function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

