# cpptree

## Introduction

In complex software systems—particularly in high-performance computing and scientific modeling—architectural structure and algorithmic logic are frequently coupled at the C Preprocessor (CPP) layer. Traditional analysis often treats source code as the linear output of a preprocessor, which discards the critical logic embedded in conditional compilation paths and macro definitions.

cpptree is designed to address this by establishing the raw combination of Code + CPP Directives as the definitive Source of Truth.

Built on `tree-sitter`, this package parses un-preprocessed source files into a unified structural tree. It treats preprocessor directives (such as `#ifdef`, `#define`, and `#include`) not as meta-data to be resolved and discarded, but as first-class structural nodes co-existing with the code blocks they govern. This approach enables developers to analyze, visualize, and transform the cpp-dependent configuration space of a codebase, capturing the complete structural intent before any instantiation occurs.