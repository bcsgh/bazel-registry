load("@rules_foreign_cc//foreign_cc:configure.bzl", "configure_make")

filegroup(
    name = "bin_source",
    srcs = glob(["**"]),
)

configure_make(
    name = "bison",
    #copts = ["-Wno-attributes"],  # 3.7.3
    lib_source = ":bin_source",
    out_binaries = ["bison"],
    visibility = ["//visibility:public"],
)
