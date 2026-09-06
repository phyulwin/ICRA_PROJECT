// frontend/scripts/check-client-secrets.mjs
// Inspect emitted browser assets for server-only credential identifiers.
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const assetRoot = join(process.cwd(), '.next', 'static');
const forbiddenMarkers = [
    'PARALLEL_API_KEY',
    'GOOGLE_APPLICATION_CREDENTIALS',
    'BEGIN PRIVATE KEY',
];

// Traverse generated static assets without reading server-only build output.
async function listFiles(directory) {
    try {
        const entries = await readdir(directory, { withFileTypes: true });
        const nested = await Promise.all(entries.map(async (entry) => {
            const path = join(directory, entry.name);
            return entry.isDirectory() ? listFiles(path) : [path];
        }));
        return nested.flat();
    } catch (error) {
        throw new Error(`Unable to inspect browser build artifacts: ${error.message}`);
    }
}

// Fail the build when a forbidden server credential marker reaches the client bundle.
async function verifyClientBundle() {
    try {
        const files = await listFiles(assetRoot);
        for (const file of files) {
            const content = await readFile(file, 'utf8');
            for (const marker of forbiddenMarkers) {
                if (content.includes(marker)) {
                    throw new Error(`Server-only credential marker found in ${file}.`);
                }
            }
        }
        console.log(`Client secret check passed across ${files.length} static assets.`);
    } catch (error) {
        console.error(error.message);
        process.exitCode = 1;
    }
}

await verifyClientBundle();
