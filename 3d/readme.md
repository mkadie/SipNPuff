# 3D Models

Mechanical models for the T-Rex Sip-N-Puff HID enclosure and assembly.

## Contents

| File | Format | Description |
|------|--------|-------------|
| `SipNPuff.step` | STEP (AP214) | First article prototype assembly — full 3D model of the electronics and enclosure concept |

## Importing the STEP File

The STEP file can be opened in any major CAD package:

- **Fusion 360** — File → Open → select `.step`
- **FreeCAD** — File → Import → select `.step`
- **SolidWorks** — File → Open → select `.step`
- **KiCad 3D Viewer** — for PCB enclosure fit checks

If you downloaded the compressed `.step.gz` version, decompress it first:

```bash
gunzip SipNPuff.step.gz
```

## Notes

- This model represents the first article prototype. Enclosure design will evolve as the project moves from breadboard to production form factor.
- See the `photos/` directory for build photos of this prototype.
- Electronics BOM, schematic, and firmware are in the project root.
