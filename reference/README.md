# Reference Briefs

Upload your filed briefs here (DOCX or PDF) so the engine can derive formatting rules.

## Directory Structure

```
reference/
└── briefs/
    ├── christopherson_appellate_brief.docx
    ├── [other_brief].docx
    └── ...
```

## Purpose

These briefs are used to:
1. Extract exact formatting patterns (margins, fonts, spacing, indentation)
2. Derive the Wisconsin appellate brief formatting rules
3. Validate that the engine produces output matching real filed briefs
4. Build test fixtures

## Uploading

From GitHub.com (desktop browser):
1. Navigate to this repo
2. Click "Add file" > "Upload files"
3. Drag DOCX files into the `reference/briefs/` directory
4. Commit to the `claude/legal-rules-engine-T9ZP3` branch
