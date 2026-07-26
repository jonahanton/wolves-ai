import { access, cp, rm } from "node:fs/promises";
import path from "node:path";

const checkedInArchive = path.resolve("public/archive");
const source = path.resolve(process.env.STATIC_ARCHIVE_DIR ?? checkedInArchive);
const destination = path.resolve("out/archive");

await access(path.join(source, "manifest.json"));
await Promise.all([
  rm(path.join(destination, "days"), { recursive: true, force: true }),
  rm(path.join(destination, "runs"), { recursive: true, force: true }),
  rm(path.join(destination, "manifest.json"), { force: true }),
  rm(path.join(destination, "provenance.json"), { force: true }),
  rm(path.join(destination, "sources"), { recursive: true, force: true }),
]);
await Promise.all([
  cp(path.join(source, "days"), path.join(destination, "days"), { recursive: true }),
  cp(path.join(source, "runs"), path.join(destination, "runs"), { recursive: true }),
  cp(path.join(source, "manifest.json"), path.join(destination, "manifest.json")),
]);
