import { access, cp, rm } from "node:fs/promises";
import path from "node:path";

const checkedInArchive = path.resolve("public/archive");
const source = path.resolve(process.env.STATIC_ARCHIVE_DIR ?? checkedInArchive);
const destination = path.resolve("out/archive");

await access(path.join(source, "manifest.json"));
if (source !== checkedInArchive) {
  await Promise.all([
    rm(path.join(destination, "days"), { recursive: true, force: true }),
    rm(path.join(destination, "runs"), { recursive: true, force: true }),
    rm(path.join(destination, "manifest.json"), { force: true }),
    rm(path.join(destination, "provenance.json"), { force: true }),
  ]);
  await cp(source, destination, { recursive: true, force: true });
}
