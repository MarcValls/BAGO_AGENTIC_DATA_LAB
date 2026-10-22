#!/usr/bin/env node
// Reproducible RFC 8785 Appendix A style reference canonicalizer.
// Primitive serialization uses ECMAScript JSON.stringify; Object.keys().sort()
// compares UTF-16 code units as required by RFC 8785 section 3.2.3.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

export function canonicalize(value) {
  const validate = (item) => {
    if (typeof item === "number" && !Number.isFinite(item)) {
      throw new TypeError("I-JSON numbers must be finite");
    }
    if (typeof item === "string") {
      for (let i = 0; i < item.length; i += 1) {
        const code = item.charCodeAt(i);
        if (code >= 0xd800 && code <= 0xdbff) {
          const next = item.charCodeAt(i + 1);
          if (!(next >= 0xdc00 && next <= 0xdfff)) throw new TypeError("lone surrogate");
          i += 1;
        } else if (code >= 0xdc00 && code <= 0xdfff) {
          throw new TypeError("lone surrogate");
        }
      }
    } else if (Array.isArray(item)) {
      item.forEach(validate);
    } else if (item !== null && typeof item === "object") {
      for (const [key, child] of Object.entries(item)) {
        validate(key);
        validate(child);
      }
    } else if (!(["boolean", "number"].includes(typeof item) || item === null)) {
      throw new TypeError("value is outside JSON data model");
    }
  };
  validate(value);

  const serialize = (item) => {
    if (item === null || typeof item !== "object") return JSON.stringify(item);
    if (Array.isArray(item)) return `[${item.map(serialize).join(",")}]`;
    return `{${Object.keys(item).sort().map((key) => `${JSON.stringify(key)}:${serialize(item[key])}`).join(",")}}`;
  };
  return serialize(value);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const document = JSON.parse(readFileSync(process.argv[2], "utf8"));
  const cases = document.jcs_golden_vectors;
  const output = [];
  for (const item of cases) {
    if (item.input !== undefined) output.push({ id: item.id, canonical_text: canonicalize(item.input) });
    if (item.numbers) {
      for (const number of item.numbers) output.push({ id: `${item.id}:${number.ieee754_hex}`, canonical_text: canonicalize(number.value) });
    }
  }
  process.stdout.write(`${JSON.stringify(output)}\n`);
}
