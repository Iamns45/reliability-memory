import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";

test("builds a self-contained AWS judge UI", async () => {
  const html = await readFile(new URL("../dist-aws-ui/index.html", import.meta.url), "utf8");
  const assets = await readdir(new URL("../dist-aws-ui/assets/", import.meta.url));

  assert.match(html, /Reliability Memory \| Resolution Operations/);
  assert.match(html, /og\.png/);
  assert.ok(
    assets.some((asset) => asset.endsWith(".js")),
    "AWS build should contain a JavaScript bundle",
  );
  assert.ok(
    assets.some((asset) => asset.endsWith(".css")),
    "AWS build should contain a CSS bundle",
  );
  assert.doesNotMatch(html, /starter preview|Your site is taking shape/i);
});
