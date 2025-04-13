import argparse
import base64
import hashlib
import json
import os

def main(args):
  M = {
    "add_build_file.patch": "../ignore/BUILD",
    "module_dot_bazel.patch": "../MODULE.bazel",
  }

  for f in args.files:
    print(f)

    if os.path.basename(f) in M:
      rel = M[os.path.basename(f)]
      src = os.path.join(os.path.dirname(f), rel)

      ver = os.path.basename(os.path.dirname(os.path.dirname(f)))

      with open(src, "r") as i:
        data = i.readlines()

      T = os.path.basename(rel)
      lines = [
        "diff --git a/%s b/%s\n" % (T, T),
        "new file mode 100644\n",
        "index 00000000..ffffffff\n",
        "--- /dev/null\n",
        "+++ b/%s\n" % T,
        "@@ -0,0 +1,%d @@\n" % len(data),
      ] + ["+%s" % l for l in data]

      patch = "".join(lines)

      with open(f, "w") as o:
        o.write(patch)

    j = os.path.join(os.path.dirname(f), "../source.json")
    with open(j, "r") as jf:
      source = json.load(jf)

    if "integrity" in source:
      intg = source["integrity"]
      del source["integrity"]
      source["integrity"] = intg

    if "patches" in source:
      intg = source["patches"]
      del source["patches"]
      source["patches"] = intg

    d = hashlib.sha256(patch.encode('utf-8')).digest()
    b64 = "sha256-%s" % base64.b64encode(d).decode("utf-8")
    source.setdefault("patches", {})[os.path.basename(f)] = b64

    if "patch_strip" in source: del source["patch_strip"]
    source["patch_strip"] = 1

    with open(j, "w") as jf:
      jf.write(json.dumps(source, indent=2) + "\n")

  return 0;


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument(
      "files", type=str, nargs="*",
      help="input files or globs for the metadata.json to process.")
  args = parser.parse_args()
  exit(main(args))
