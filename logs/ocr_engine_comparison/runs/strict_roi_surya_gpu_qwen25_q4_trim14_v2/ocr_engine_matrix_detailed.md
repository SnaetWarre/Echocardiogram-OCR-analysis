# OCR Engine Detailed Per-File Report

_This report is intended for line-level academic error analysis._

## labels / surya / raw_no_parser

### 94106955_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Diam 3.2 cm`

#### Predicted output
- `1 Ao Diam 3.2 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 40] ocr_bbox=(0, 19, 162, 26) confidence=0.9188

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0011.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0012.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0012.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVOT Diam 2.0 cm`

#### Predicted output
- `1 LVOT Diam 2.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 184, 41] ocr_bbox=(0, 18, 184, 27) confidence=0.9003

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0012.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0013.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0013.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LA Diam 4.0 cm`

#### Predicted output
- `1 LA Diam 4.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 40] ocr_bbox=(0, 19, 162, 26) confidence=0.9188

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0013.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0014.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao asc 3.2 cm`

#### Predicted output
- `1 Ao asc 3.2 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 150, 42] ocr_bbox=(0, 17, 150, 28) confidence=0.8968

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0014.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0016.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0016.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `IVSd 0.9 cm`
- `LVIDd 5.4 cm`
- `LVPWd 1.0 cm`

#### Predicted output
- `1 IVSd`
- `0.9 cm`
- `LVIDd`
- `5.4 cm`
- `LVPWd 1.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 153, 85] ocr_bbox=(0, 17, 153, 71) confidence=0.9496

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0016.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `IVSd 0.9 cm` | actual: `0.9 cm`
- `wrong_label_for_value` | expected: `LVIDd 5.4 cm` | actual: `5.4 cm`

### 94106955_0017.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0017.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVIDs 3.6 cm`
- `EF(Teich) 62 %`
- `%FS 34 %`

#### Predicted output
- `1 LVIDs_`
- `3.6 cm`
- `EF(Teich) 62 %`
- `34 %`
- `%FS`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 154, 85] ocr_bbox=(0, 17, 154, 71) confidence=0.9499

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0017.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVIDs 3.6 cm` | actual: `3.6 cm`
- `wrong_label_for_value` | expected: `%FS 34 %` | actual: `34 %`

### 94106955_0021.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0021.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 1.9 m/s`
- `TR maxPG 14 mmHg`

#### Predicted output
- `1 TR Vmax`
- `1.9 \, \text{m/s}`
- `TR maxPG 14 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0021.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 1.9 m/s` | actual: `1.9 \. \text{m/s}`

### 94106955_0024.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0024.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `PV Vmax 0.87 m/s`
- `PV maxPG 3 mmHg`

#### Predicted output
- `1 PV Vmax 0.87 m/s`
- `PV maxPG 3 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 192, 63] ocr_bbox=(0, 17, 192, 49) confidence=0.9364

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0024.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0028.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0028.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `PV Vmax 0.96 m/s`
- `PV maxPG 4 mmHg`

#### Predicted output
- `1 PV Vmax 0.96 m/s`
- `PV maxPG 4 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 192, 63] ocr_bbox=(0, 17, 192, 49) confidence=0.9364

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0028.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0034.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0034.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.3 m/s`
- `TR maxPG 21 mmHg`

#### Predicted output
- `1 TR Vmax`
- `2.3 m/s`
- `TR maxPG 21 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0034.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.3 m/s` | actual: `2.3 m/s`

### 94106955_0035.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0035.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 1.9 m/s`
- `Tr maxPG 14 mmHg`

#### Predicted output
- `1 TR Vmax`
- `1.9 \, \text{m/s}`
- `TR maxPG 14 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0035.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 1.9 m/s` | actual: `1.9 \. \text{m/s}`

### 94106955_0044.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0044.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `RA LENGTH 5.9 cm`
- `LA LENGTH 6.6 cm`

#### Predicted output
- `2 RA LENGTH 5.9 cm`
- `1 LA LENGTH 6.6 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 189, 62] ocr_bbox=(0, 19, 189, 48) confidence=0.9491

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0044.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0046.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `MV E VEL 0.7 m/s`
- `MV DecT 183 ms`
- `MV Dec Slope 4 m/s`
- `MV A Vel 0.6 m/s`
- `MV E/A Ratio 1.2`

#### Predicted output
- `0.7 \, \mathrm{m/s}`
- `1 MV E Vel`
- `MV DecT`
- `183 ms`
- `MV Dec Slope 4 m/s2`
- `MV A Vel`
- `0.6 \, \mathrm{m/s}`
- `MV E/A Ratio`
- `1.2`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 206, 127] ocr_bbox=(0, 17, 206, 113) confidence=0.9645

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0046.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `MV E VEL 0.7 m/s` | actual: `0.7 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV DecT 183 ms` | actual: `183 ms`
- `wrong_label_for_value` | expected: `MV A Vel 0.6 m/s` | actual: `0.6 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV E/A Ratio 1.2` | actual: `1.2`

### 94106955_0050.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0050.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `P Vein A 0.3 m/s`
- `P vein D 0.4 m/s`
- `P Vein S/D Ratio 1.2`
- `P Vein S 0.5 m/s`

#### Predicted output
- `3 P Vein A`
- `0.3 \, \mathrm{m/s}`
- `2 P Vein D`
- `0.4 \,\mathrm{m/s}`
- `P Vein S/D Ratio 1.2`
- `1 P Vein S`
- `0.5 \, \mathrm{m/s}`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 195, 107] ocr_bbox=(0, 18, 195, 93) confidence=0.9625

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0050.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `P Vein A 0.3 m/s` | actual: `0.3 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `P vein D 0.4 m/s` | actual: `0.4 \.\mathrm{m/s}`
- `wrong_label_for_value` | expected: `P Vein S 0.5 m/s` | actual: `0.5 \. \mathrm{m/s}`

### 94106955_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0051.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 2
- ROI detected: True

#### Expected lines
- `LALs A4C 5.8 cm`
- `LAAs A4C 19.5 cm`
- `LAESV A-L A4C 56 ml`

#### Predicted output
- `1 LALS A4C`
- `5.8 cm`
- `LAAs A4C 19.5 cm2`
- `LAESV A-L A4C 56 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 211, 84] ocr_bbox=(0, 18, 211, 70) confidence=0.9533

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0051.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LALs A4C 5.8 cm` | actual: `5.8 cm`

### 94106955_0053.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0053.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVLd A4C 7.18 cm`
- `LVEDV MOD A4C 105.47 ml`

#### Predicted output
- `1 LVLd A4C`
- `7.18 cm`
- `LVEDV MOD A4C 105.47 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 256, 63] ocr_bbox=(0, 17, 256, 49) confidence=0.9399

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0053.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVLd A4C 7.18 cm` | actual: `7.18 cm`

### 94106955_0054.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0054.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVEF MOD A4C 63.66 %`
- `SV MOD A4C 67.14 ml`
- `LVLs A4C 5.93 cm`
- `LVESV MOD A4C 38.32 ml`

#### Predicted output
- `LVEF MOD A4C`
- `63.66\%`
- `SV MOD A4C`
- `67.14 ml`
- `1 LVLs A4C`
- `5.93 cm`
- `LVESV MOD A4C 38.32 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 245, 105] ocr_bbox=(0, 19, 245, 91) confidence=0.9730

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0054.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVEF MOD A4C 63.66 %` | actual: `63.66\%`
- `wrong_label_for_value` | expected: `SV MOD A4C 67.14 ml` | actual: `67.14 ml`
- `wrong_label_for_value` | expected: `LVLs A4C 5.93 cm` | actual: `5.93 cm`

### 94106955_0055.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0055.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `E' Lat 0.09 m/s`

#### Predicted output
- `1 E' Lat 0.09 m/s`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 154, 42] ocr_bbox=(0, 17, 154, 28) confidence=0.8976

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0055.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0056.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0056.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `E' Sept 0.08 m/s`

#### Predicted output
- `E' Sept 0.08 m/s`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 165, 41] ocr_bbox=(0, 18, 165, 27) confidence=0.8976

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0056.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0061.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0061.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVOT Vmax 1.1 m/s`
- `LVOT maxPG 5 mmHg`
- `LVOT VTI 19.9 cm`

#### Predicted output
- `1 LVOT Vmax`
- `1.1 m/s`
- `LVOT maxPG 5 mmHg`
- `LVOT VTI`
- `19.9 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 215, 84] ocr_bbox=(0, 18, 215, 70) confidence=0.9535

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0061.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVOT Vmax 1.1 m/s` | actual: `1.1 m/s`
- `wrong_label_for_value` | expected: `LVOT VTI 19.9 cm` | actual: `19.9 cm`

### 94106955_0062.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0062.dcm`
- Labels: 7
- Full matches: 0
- Value matches: 7
- Name matches: 1
- ROI detected: True

#### Expected lines
- `AVA Vmax 2.8 cm`
- `AVA (VTI) 2.3 cm`
- `AV Vmax 1.3 m/s`
- `AV Vmean 1.0 m/s`
- `AV maxPG 6 mmHg`
- `AV meanPG 4 mmHg`
- `AV VTI 28 cm`

#### Predicted output
- `AVA Vmax`
- `2.8 cm2`
- `2.3 cm2`
- `AVA (VTI)`
- `1 AV Vmax`
- `1.3 \, \text{m/s}`
- `AV Vmean`
- `1.0 \, \text{m/s}`
- `AV maxPG`
- `6 mmHa`
- `AV meanPG`
- `4 mmHq`
- `AV VTI`
- `28 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 204, 170] ocr_bbox=(0, 18, 204, 156) confidence=0.9767

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0062.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `AVA Vmax 2.8 cm` | actual: `2.8 cm2`
- `wrong_label_for_value` | expected: `AVA (VTI) 2.3 cm` | actual: `2.3 cm2`
- `wrong_label_for_value` | expected: `AV Vmax 1.3 m/s` | actual: `1.3 \. \text{m/s}`
- `partial_mismatch` | expected: `AV Vmean 1.0 m/s` | actual: `1.0 \. \text{m/s}`
- `wrong_label_for_value` | expected: `AV maxPG 6 mmHg` | actual: `6 mmha`
- `wrong_label_for_value` | expected: `AV meanPG 4 mmHg` | actual: `4 mmhq`
- `wrong_label_for_value` | expected: `AV VTI 28 cm` | actual: `28 cm`

### 94106955_0064.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0064.dcm`
- Labels: 5
- Full matches: 0
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `AV Vmax 1.1 m/s`
- `AV Vmean 0.9 m/s`
- `AV maxPG 5 mmHg`
- `AV meanPG 3 mmHg`
- `AV VTI 28 cm`

#### Predicted output
- `1 AV Vmax`
- `1.1 m/s`
- `AV Vmean`
- `0.9 \, \text{m/s}`
- `AV maxPG`
- `5 mmHg`
- `AV meanPG 3 mmHq`
- `AV VTI`
- `28 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 204, 126] ocr_bbox=(0, 18, 204, 112) confidence=0.9687

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0064.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `AV Vmax 1.1 m/s` | actual: `1.1 m/s`
- `wrong_label_for_value` | expected: `AV Vmean 0.9 m/s` | actual: `0.9 \. \text{m/s}`
- `wrong_label_for_value` | expected: `AV maxPG 5 mmHg` | actual: `5 mmhg`
- `wrong_unit` | expected: `AV meanPG 3 mmHg` | actual: `av meanpg 3 mmhq`
- `wrong_label_for_value` | expected: `AV VTI 28 cm` | actual: `28 cm`

### 94106955_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0066.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `RVIDd 3.2 cm`

#### Predicted output
- `ı RVIDd 3.2 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 142, 40] ocr_bbox=(0, 19, 142, 26) confidence=0.9144

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0066.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0069.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0069.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.1 m/s`
- `TR maxPG 17 mmHg`

#### Predicted output
- `1 TR Vmax`
- `2.1 m/s`
- `TR maxPG 17 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0069.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.1 m/s` | actual: `2.1 m/s`

### 94106955_0071.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0071.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LAESV(A-L) 70.05 ml`
- `LAESV Index (A-L) 31.99 ml/m2`
- `LALs A2C 6.0 cm`
- `LAAs A2C 24 cm`
- `LAESV A-L A2C 84.0 ml`

#### Predicted output
- `LAESV(A-L)`
- `70.05 ml`
- `LAESV Index (A-L) 31.99 ml/m2`
- `1 LALS A2C`
- `6.0 cm`
- `LAAs A2C`
- `24 cm2`
- `LAESV A-L A2C`
- `84.0 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 289, 128] ocr_bbox=(0, 17, 289, 114) confidence=0.9679

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0071.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LAESV(A-L) 70.05 ml` | actual: `70.05 ml`
- `wrong_label_for_value` | expected: `LALs A2C 6.0 cm` | actual: `6.0 cm`
- `wrong_label_for_value` | expected: `LAAs A2C 24 cm` | actual: `24 cm2`
- `wrong_label_for_value` | expected: `LAESV A-L A2C 84.0 ml` | actual: `84.0 ml`

### 94106955_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0074.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVLd A2C 7.76 cm`
- `LVEDV MOD A2C 93.58 ml`

#### Predicted output
- `1 LVLd A2C`
- `7.76 cm`
- `LVEDV MOD A2C 93.58 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 246, 63] ocr_bbox=(0, 17, 246, 49) confidence=0.9396

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0074.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVLd A2C 7.76 cm` | actual: `7.76 cm`

### 94106955_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0075.dcm`
- Labels: 7
- Full matches: 0
- Value matches: 7
- Name matches: 0
- ROI detected: True

#### Expected lines
- `EF Biplane 64 %`
- `LVEDV MOD BP 102 ml`
- `LVESV MOD BP 37 ml`
- `LVEF MOD A2C 62.09 %`
- `SV MOD A2C 58.10 ml`
- `LVLs A2C 6.07 cm`
- `LVESV MOD A2C 35.48 ml`

#### Predicted output
- `EF Biplane`
- `64 %`
- `LVEDV MOD BP`
- `102 ml`
- `LVESV MOD BP`
- `37 ml`
- `LVEF MOD A2C`
- `62.09 %`
- `SV MOD A2C`
- `58.10 ml`
- `1 LVLs A2C`
- `6.07 cm`
- `LVESV MOD A2C`
- `35.48 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 245, 170] ocr_bbox=(0, 19, 245, 156) confidence=0.9833

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0075.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `EF Biplane 64 %` | actual: `64 %`
- `wrong_label_for_value` | expected: `LVEDV MOD BP 102 ml` | actual: `102 ml`
- `wrong_label_for_value` | expected: `LVESV MOD BP 37 ml` | actual: `37 ml`
- `wrong_label_for_value` | expected: `LVEF MOD A2C 62.09 %` | actual: `62.09 %`
- `wrong_label_for_value` | expected: `SV MOD A2C 58.10 ml` | actual: `58.10 ml`
- `wrong_label_for_value` | expected: `LVLs A2C 6.07 cm` | actual: `6.07 cm`
- `wrong_label_for_value` | expected: `LVESV MOD A2C 35.48 ml` | actual: `35.48 ml`

### 94106955_0090.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0090.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 1
- Name matches: 0
- ROI detected: True

#### Expected lines
- `IVC 2.2 cm`

#### Predicted output
- `2.2 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 119, 40] ocr_bbox=(0, 19, 119, 26) confidence=0.9080

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0090.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `IVC 2.2 cm` | actual: `2.2 cm`

### 94106955_0092.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0092.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Desc Diam 2.6 cm`

#### Predicted output
- `1 Ao Desc Diam 2.6 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 209, 42] ocr_bbox=(0, 17, 209, 28) confidence=0.9060

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0092.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0096.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0096.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Arch Diam 2.8 cm`

#### Predicted output
- `1 Ao Arch Diam 2.8 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 206, 41] ocr_bbox=(0, 19, 206, 27) confidence=0.9035

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0096.dcm__frame_000.png`

#### Mismatches
- none

### 94106955_0099.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0099.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: True

#### Expected lines
- `L 2.37 cm`

#### Predicted output
- `37 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 20, 105, 39] ocr_bbox=(0, 34, 105, 25) confidence=0.8801

#### ROI visualizations
- `roi_visualizations/labels/surya/raw_no_parser/94106955_0099.dcm__frame_000.png`

#### Mismatches
- `missing_prediction` | expected: `L 2.37 cm` | actual: `NOT FOUND`

## labels / surya / regex_parser

### 94106955_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0012.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0012.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0013.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0013.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0014.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0016.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0016.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0017.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0017.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0021.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0021.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0024.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0024.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0028.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0028.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0034.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0034.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0035.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0035.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0044.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0044.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0046.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0050.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0050.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0051.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0053.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0053.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0054.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0054.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0055.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0055.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0056.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0056.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0061.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0061.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0062.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0062.dcm`
- Labels: 7
- Full matches: 3
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0064.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0064.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0066.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0069.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0069.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0071.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0071.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0074.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0075.dcm`
- Labels: 7
- Full matches: 7
- Value matches: 7
- Name matches: 7
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0090.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0090.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0092.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0092.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0096.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0096.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0099.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0099.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

## labels / surya / local_llm_parser

### 94106955_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0012.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0012.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0013.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0013.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0014.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0016.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0016.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0017.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0017.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0021.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0021.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0024.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0024.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0028.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0028.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0034.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0034.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0035.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0035.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0044.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0044.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0046.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 5
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0050.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0050.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0051.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0053.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0053.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0054.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0054.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0055.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0055.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0056.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0056.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0061.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0061.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0062.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0062.dcm`
- Labels: 7
- Full matches: 4
- Value matches: 6
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0064.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0064.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0066.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0069.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0069.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0071.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0071.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0074.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0075.dcm`
- Labels: 7
- Full matches: 7
- Value matches: 7
- Name matches: 7
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0090.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0090.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 1
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0092.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0092.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0096.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0096.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 94106955_0099.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002221/s94106955/94106955_0099.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

## validation_labels / surya / raw_no_parser

### 92290733_0003.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0003.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `IVSD 1.1 cm`
- `LVIDD 5.0 cm`
- `LVPWD 1.1 cm`

#### Predicted output
- `1 IVSd`
- `1.1 cm`
- `LVIDd`
- `5.0 cm`
- `LVPWd 1.1 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 153, 86] ocr_bbox=(0, 17, 153, 72) confidence=0.9381

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0003.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `IVSD 1.1 cm` | actual: `lvpwd 1.1 cm`
- `wrong_label_for_value` | expected: `LVIDD 5.0 cm` | actual: `5.0 cm`

### 92290733_0004.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0004.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `2 LA Diam 5.5 cm`
- `LVIDS 4.2 cm`
- `EF (Teich) 34 %`
- `%FS 16 %`

#### Predicted output
- `2 LA Diam 5.5 cm`
- `1 LVIDs`
- `4.2 cm`
- `EF(Teich)`
- `34 %`
- `16 %`
- `%FS`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 105] ocr_bbox=(0, 19, 162, 91) confidence=0.9692

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0004.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVIDS 4.2 cm` | actual: `4.2 cm`
- `wrong_label_for_value` | expected: `EF (Teich) 34 %` | actual: `34 %`
- `wrong_label_for_value` | expected: `%FS 16 %` | actual: `16 %`

### 92290733_0007.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0007.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVOT Diam 2.0 cm`

#### Predicted output
- `1 LVOT Diam 2.0 cm`
- `. . . . . . . . . . . . . . . . . . . .`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 184, 42] ocr_bbox=(0, 18, 184, 28) confidence=0.8791

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0007.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao asc 3.0 cm`

#### Predicted output
- `1 Ao asc 3.0 cm`
- `. .`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 150, 43] ocr_bbox=(0, 17, 150, 29) confidence=0.8761

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0008.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0010.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0010.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Diam 3.1 cm`

#### Predicted output
- `1 Ao Diam 3.1 cm`
- `. .`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 41] ocr_bbox=(0, 19, 162, 27) confidence=0.8967

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0010.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0014.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 3.4 m/s`
- `TR maxPG 47 mmHg`

#### Predicted output
- `1 TR Vmax`
- `3.4 m/s`
- `TR maxPG 47 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0014.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 3.4 m/s` | actual: `3.4 m/s`

### 92290733_0019.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0019.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.7 m/s`
- `TR maxPG 29 mmHg`

#### Predicted output
- `2.7 m/s`
- `1 TR Vmax`
- `TR maxPG 29 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0019.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.7 m/s` | actual: `2.7 m/s`

### 92290733_0030.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0030.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `2 RA LENGTH 6.1 cm`
- `1 LA LENGTH 6.0 cm`

#### Predicted output
- `2 RA LENGTH 6.1 cm`
- `1 LA LENGTH 6.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 189, 62] ocr_bbox=(0, 19, 189, 48) confidence=0.9491

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0030.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0032.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0032.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `E' Lat 0.06 m/s`

#### Predicted output
- `1 E' Lat 0.06 m/s`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 154, 43] ocr_bbox=(0, 17, 154, 29) confidence=0.8759

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0032.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0033.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0033.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `E' Sept 0.06 m/s`

#### Predicted output
- `1 E' Sept 0.06 m/s`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 165, 42] ocr_bbox=(0, 18, 165, 28) confidence=0.8760

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0033.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0035.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0035.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `MV E Vel 0.8 m/s`
- `MV DecT 287 ms`
- `MV Dec Slope 3 m/s`
- `MV A Vel 1.2 m/s`
- `MV E/A Ratio 0.7`

#### Predicted output
- `1 MV E Vel`
- `0.8 \, \mathrm{m/s}`
- `MV Decl`
- `287 ms`
- `MV Dec Slope 3 m/s2`
- `MV A Vel`
- `1.2 \, \mathrm{m/s}`
- `MV E/A Ratio`
- `0.7`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 206, 127] ocr_bbox=(0, 17, 206, 113) confidence=0.9645

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0035.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `MV E Vel 0.8 m/s` | actual: `0.8 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV DecT 287 ms` | actual: `287 ms`
- `wrong_label_for_value` | expected: `MV A Vel 1.2 m/s` | actual: `1.2 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV E/A Ratio 0.7` | actual: `0.7`

### 92290733_0040.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0040.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `P Vein D 0.7 m/s`
- `P Vein S/D Ratio 0.5`
- `P Vein S 0.4 m/s`

#### Predicted output
- `2 P Vein D`
- `0.7 \, \mathrm{m/s}`
- `P Vein S/D Ratio 0.5`
- `1 P Vein S`
- `0.4 \text{ m/s}`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 195, 84] ocr_bbox=(0, 18, 195, 70) confidence=0.9526

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0040.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `P Vein D 0.7 m/s` | actual: `0.7 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `P Vein S 0.4 m/s` | actual: `0.4 \text{ m/s}`

### 92290733_0045.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0045.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVOT Vmax 0.9 m/s`
- `LVOT maxPG 3 mmHg`
- `LVOT VTI 17.6 cm`

#### Predicted output
- `1 LVOT Vmax`
- `0.9 \, \mathrm{m/s}`
- `LVOT maxPG 3 mmHg`
- `LVOT VTI`
- `17.6 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 215, 85] ocr_bbox=(0, 18, 215, 71) confidence=0.9420

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0045.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVOT Vmax 0.9 m/s` | actual: `0.9 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `LVOT VTI 17.6 cm` | actual: `17.6 cm`

### 92290733_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0046.dcm`
- Labels: 7
- Full matches: 0
- Value matches: 7
- Name matches: 0
- ROI detected: True

#### Expected lines
- `AV Vmax 2.1 cm`
- `AV (VTI) 1.8 cm`
- `1 AV Vmax 1.5 m/s`
- `AV Vmean 1.1 m/s`
- `AV maxPG 9 mmHg`
- `AV meanPG 5 mmHg`
- `AV VTI 33 cm`

#### Predicted output
- `AVA Vmax`
- `2.1 cm2`
- `AVA (VTI)`
- `1.8 cm2`
- `1 AV Vmax`
- `1.5 \,\mathrm{m/s}`
- `AV Vmean`
- `1.1 m/s`
- `AV maxPG`
- `9 mmHa`
- `AV meanPG`
- `5 mmHg`
- `AV VTI`
- `33 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 204, 170] ocr_bbox=(0, 18, 204, 156) confidence=0.9767

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0046.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `AV Vmax 2.1 cm` | actual: `2.1 cm2`
- `wrong_label_for_value` | expected: `AV (VTI) 1.8 cm` | actual: `1.8 cm2`
- `wrong_label_for_value` | expected: `1 AV Vmax 1.5 m/s` | actual: `1.5 \.\mathrm{m/s}`
- `wrong_label_for_value` | expected: `AV Vmean 1.1 m/s` | actual: `1.1 m/s`
- `wrong_label_for_value` | expected: `AV maxPG 9 mmHg` | actual: `9 mmha`
- `wrong_label_for_value` | expected: `AV meanPG 5 mmHg` | actual: `5 mmhg`
- `wrong_label_for_value` | expected: `AV VTI 33 cm` | actual: `33 cm`

### 92290733_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0051.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.5 m/s`
- `TR maxPG 25 mmHg`

#### Predicted output
- `1 TR Vmax`
- `2.5 m/s`
- `TR maxPG 25 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0051.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.5 m/s` | actual: `2.5 m/s`

### 92290733_0071.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0071.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Arch Diam 2.9 cm`

#### Predicted output
- `1 Ao Arch Diam 2.9 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 206, 41] ocr_bbox=(0, 19, 206, 27) confidence=0.9035

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0071.dcm__frame_000.png`

#### Mismatches
- none

### 92290733_0072.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0072.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVLd A4C 7.78 cm`
- `LVEDV MOD A4C 139.52 ml`

#### Predicted output
- `1 LVLd A4C`
- `7.78 cm`
- `LVEDV MOD A4C 139.52 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 256, 63] ocr_bbox=(0, 17, 256, 49) confidence=0.9399

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0072.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVLd A4C 7.78 cm` | actual: `7.78 cm`

### 92290733_0073.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0073.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVEF MOD A4C 50.26 %`
- `SV MOD A4C 70.11 ml`
- `1 LVLs A4C 6.29 cm`
- `LVESV MOD A4C 69.40 ml`

#### Predicted output
- `LVEF MOD A4C`
- `50.26 \%`
- `SV MOD A4C`
- `70.11 ml`
- `1 LVLs A4C`
- `6.29 cm`
- `LVESV MOD A4C \,\, 69.40 ml \,`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 245, 105] ocr_bbox=(0, 19, 245, 91) confidence=0.9730

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0073.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVEF MOD A4C 50.26 %` | actual: `50.26 \%`
- `wrong_label_for_value` | expected: `SV MOD A4C 70.11 ml` | actual: `70.11 ml`
- `wrong_label_for_value` | expected: `1 LVLs A4C 6.29 cm` | actual: `6.29 cm`

### 92290733_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0074.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LALs A4C 6.7 cm`
- `LAAs A4C 29.0 cm`
- `LAESV A-L A4C 106 ml`

#### Predicted output
- `1 LALS A4C`
- `6.7 cm`
- `LAAs A4C`
- `29.0 cm2`
- `LAESV A-L A4C 106 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 221, 83] ocr_bbox=(0, 19, 221, 69) confidence=0.9648

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0074.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LALs A4C 6.7 cm` | actual: `6.7 cm`
- `wrong_label_for_value` | expected: `LAAs A4C 29.0 cm` | actual: `29.0 cm2`

### 92290733_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0075.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVLd A2C 7.89 cm`
- `LVEDV MOD A2C 107.73 ml`

#### Predicted output
- `1 LVLd A2C`
- `7.89 cm`
- `LVEDV MOD A2C 107.73 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 256, 63] ocr_bbox=(0, 17, 256, 49) confidence=0.9399

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0075.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVLd A2C 7.89 cm` | actual: `7.89 cm`

### 92290733_0076.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0076.dcm`
- Labels: 9
- Full matches: 0
- Value matches: 9
- Name matches: 0
- ROI detected: True

#### Expected lines
- `R-R 0.00 m/s`
- `CO Biplane 0.00`
- `Biplane EF 49 %`
- `LVEDV MOD BP 123 ml`
- `LVESV MOD BP 63 ml`
- `Biplane LVEF 51.53 %`
- `Biplane SV 55.51 ml`
- `LVLs A2C 7.04 cm`
- `LVESV MOD A2C 52.22 ml`

#### Predicted output
- `0.00 ms`
- `2 R-R`
- `HR`
- `CO Biplane`
- `0.00 l/min`
- `EF Biplane`
- `49 %`
- `LVEDV MOD BP`
- `123 ml`
- `LVESV MOD BP`
- `63 ml`
- `LVEF MOD A2C`
- `51.53 %`
- `SV MOD A2C`
- `55.51 ml`
- `1 LVLs A2C`
- `7.04 cm`
- `LVESV MOD A2C`
- `52.22 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 245, 235] ocr_bbox=(0, 19, 245, 221) confidence=0.9879

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0076.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `R-R 0.00 m/s` | actual: `0.00 l/min`
- `wrong_label_for_value` | expected: `CO Biplane 0.00` | actual: `0.00 l/min`
- `wrong_label_for_value` | expected: `Biplane EF 49 %` | actual: `49 %`
- `wrong_label_for_value` | expected: `LVEDV MOD BP 123 ml` | actual: `123 ml`
- `wrong_label_for_value` | expected: `LVESV MOD BP 63 ml` | actual: `63 ml`
- `wrong_label_for_value` | expected: `Biplane LVEF 51.53 %` | actual: `51.53 %`
- `wrong_label_for_value` | expected: `Biplane SV 55.51 ml` | actual: `55.51 ml`
- `wrong_label_for_value` | expected: `LVLs A2C 7.04 cm` | actual: `7.04 cm`
- `wrong_label_for_value` | expected: `LVESV MOD A2C 52.22 ml` | actual: `52.22 ml`

### 92290733_0077.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0077.dcm`
- Labels: 6
- Full matches: 1
- Value matches: 6
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LAAs A4C 0.0 cm`
- `LAESV (A-L) 97.69 ml`
- `LAESV Index (A-L) 57.13 ml/m2`
- `LALs A2C 6.6 cm`
- `LAAs A2C 26 cm`
- `LAESV A-L A2C 87.6 ml`

#### Predicted output
- `2 LAAs A4C`
- `0.0 cm2`
- `LAESV(A-L)`
- `97.69 ml`
- `LAESV Index (A-L) 57.13 ml/m2`
- `1 LALS A2C`
- `6.6 cm`
- `LAAs A2C`
- `26 cm2`
- `LAESV A-L A2C`
- `87.6 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 289, 150] ocr_bbox=(0, 17, 289, 136) confidence=0.9721

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0077.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LAAs A4C 0.0 cm` | actual: `0.0 cm2`
- `wrong_label_for_value` | expected: `LAESV (A-L) 97.69 ml` | actual: `97.69 ml`
- `wrong_label_for_value` | expected: `LALs A2C 6.6 cm` | actual: `6.6 cm`
- `wrong_label_for_value` | expected: `LAAs A2C 26 cm` | actual: `26 cm2`
- `wrong_label_for_value` | expected: `LAESV A-L A2C 87.6 ml` | actual: `87.6 ml`

### 92290733_0078.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0078.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 1
- Name matches: 0
- ROI detected: True

#### Expected lines
- `RIVDd 3.5 cm`

#### Predicted output
- `1 RVIDd 3.5 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 142, 41] ocr_bbox=(0, 19, 142, 27) confidence=0.8920

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0078.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `RIVDd 3.5 cm` | actual: `1 rvidd 3.5 cm`

### 92290733_0079.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0079.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: True

#### Expected lines
- `L 4.20 cm`

#### Predicted output
- `.20 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 21, 102, 37] ocr_bbox=(0, 35, 102, 23) confidence=0.8983

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/92290733_0079.dcm__frame_000.png`

#### Mismatches
- `missing_prediction` | expected: `L 4.20 cm` | actual: `NOT FOUND`

### 98667422_0002.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0002.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Desc Diam 2.0 cm`

#### Predicted output
- `1 Ao Desc Diam 2.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 216, 43] ocr_bbox=(0, 18, 216, 29) confidence=0.9986

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0002.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0005.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0005.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVOT Diam 2.0 cm`

#### Predicted output
- `1 LVOT Diam 2.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 190, 44] ocr_bbox=(0, 18, 190, 30) confidence=0.8839

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0005.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0006.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0006.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `2 LA Diam 5.1 cm`
- `1 Ao Diam 3.0 cm`

#### Predicted output
- `2 LA Diam 5.1 cm`
- `1 Ao Diam 3.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 167, 66] ocr_bbox=(0, 18, 167, 52) confidence=0.9992

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0006.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0007.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0007.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `IVSd 0.7 cm`
- `LVIDd 5.1 cm`
- `LVPWd 0.8 cm`

#### Predicted output
- `1 IVSd`
- `0.7 cm`
- `LVIDd`
- `5.1 cm`
- `LVPWd 0.8 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 158, 87] ocr_bbox=(0, 18, 158, 73) confidence=0.9967

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0007.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `IVSd 0.7 cm` | actual: `0.7 cm`
- `wrong_label_for_value` | expected: `LVIDd 5.1 cm` | actual: `5.1 cm`

### 98667422_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0008.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVIDs 3.9 cm`
- `EF (Teich) 45 %`
- `%FS 22 %`
- `SV (Teich) 54.4 ml`

#### Predicted output
- `1 LVIDs`
- `3.9 cm`
- `EF(Teich)`
- `45 %`
- `%FS`
- `22 %`
- `SV(Teich) 54.4 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 181, 110] ocr_bbox=(0, 18, 181, 96) confidence=0.9533

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0008.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVIDs 3.9 cm` | actual: `3.9 cm`
- `wrong_label_for_value` | expected: `EF (Teich) 45 %` | actual: `45 %`
- `wrong_label_for_value` | expected: `%FS 22 %` | actual: `22 %`

### 98667422_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao asc 3.0 cm`

#### Predicted output
- `1 Ao asc 3.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 155, 44] ocr_bbox=(0, 18, 155, 30) confidence=0.9752

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0011.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0014.dcm`
- Labels: 2
- Full matches: 0
- Value matches: 2
- Name matches: 0
- ROI detected: True

#### Expected lines
- `V 3.08 m/s`
- `P 37.98 mmHg`

#### Predicted output
- `3.08 \, \mathrm{m/s}`
- `+\mathbf{v}`
- `p 37.98 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 155, 65] ocr_bbox=(0, 18, 155, 51) confidence=0.9333

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0014.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `V 3.08 m/s` | actual: `3.08 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `P 37.98 mmHg` | actual: `p 37.98 mmhg`

### 98667422_0025.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0025.dcm`
- Labels: 2
- Full matches: 0
- Value matches: 2
- Name matches: 0
- ROI detected: True

#### Expected lines
- `v 2.85 m/s`
- `p 32.56 mmHg`

#### Predicted output
- `2.85 \,\mathrm{m/s}`
- `+\mathbf{v}`
- `p 32.56 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 155, 65] ocr_bbox=(0, 18, 155, 51) confidence=0.9333

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0025.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `v 2.85 m/s` | actual: `2.85 \.\mathrm{m/s}`
- `wrong_label_for_value` | expected: `p 32.56 mmHg` | actual: `p 32.56 mmhg`

### 98667422_0036.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0036.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `RA length 7.2 cm`
- `La length 7.0`

#### Predicted output
- `2 RA length 7.2 cm`
- `1 LA length 7.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 177, 66] ocr_bbox=(0, 18, 177, 52) confidence=0.9994

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0036.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0037.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0037.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LALs A4C 7.1 cm`
- `LAAs A4C 31 cm`
- `LAESV A-L A4C 114.4 ml`

#### Predicted output
- `1 LALS A4C`
- `7.1 cm`
- `LAAs A4C`
- `31 cm2`
- `LAESV A-L A4C 114.4 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 244, 87] ocr_bbox=(0, 18, 244, 73) confidence=0.9559

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0037.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LALs A4C 7.1 cm` | actual: `7.1 cm`
- `wrong_label_for_value` | expected: `LAAs A4C 31 cm` | actual: `31 cm2`

### 98667422_0038.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0038.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `RVIDd 5.6 cm`

#### Predicted output
- `1 RVIDd 5.6 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 147, 43] ocr_bbox=(0, 18, 147, 29) confidence=0.8970

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0038.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0039.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0039.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LAESV (A-L) 96.5 ml`
- `LAESV Index (A-L) 60.3 ml/m2`
- `1 LALs A2C 7.1 cm`
- `LAAs A2C 26 cm`
- `LAESV A-L A2C 81 ml`

#### Predicted output
- `LAESV(A-L)`
- `96.5 ml`
- `LAESV Index (A-L) 60.3 ml/m2`
- `1 LALS A2C`
- `7.1 cm`
- `26 cm2`
- `LAAs A2C`
- `LAESV A-L A2C`
- `81 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 288, 132] ocr_bbox=(0, 18, 288, 118) confidence=0.9992

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0039.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LAESV (A-L) 96.5 ml` | actual: `96.5 ml`
- `wrong_label_for_value` | expected: `1 LALs A2C 7.1 cm` | actual: `7.1 cm`
- `wrong_label_for_value` | expected: `LAAs A2C 26 cm` | actual: `26 cm2`
- `wrong_label_for_value` | expected: `LAESV A-L A2C 81 ml` | actual: `81 ml`

### 98667422_0040.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0040.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVLd A4C 7.70 cm`
- `LVEDV MOD A4C 118.01 ml`

#### Predicted output
- `1 LVLd A4C`
- `7.70 cm`
- `LVEDV MOD A4C 118.01 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 264, 65] ocr_bbox=(0, 18, 264, 51) confidence=0.9416

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0040.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVLd A4C 7.70 cm` | actual: `7.70 cm`

### 98667422_0041.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0041.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVEF MOD A4C 33.70 %`
- `SV MOD A4C 39.77 ml`
- `1 LVLs A4C 7.18 cm`
- `LVESV MOD A4C 78.24 ml`

#### Predicted output
- `LVEF MOD A4C`
- `33.70 %`
- `SV MOD A4C`
- `39.77 ml`
- `1 LVLs A4C`
- `7.18 cm`
- `LVESV MOD A4C 78.24 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 253, 110] ocr_bbox=(0, 18, 253, 96) confidence=0.9649

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0041.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVEF MOD A4C 33.70 %` | actual: `33.70 %`
- `wrong_label_for_value` | expected: `SV MOD A4C 39.77 ml` | actual: `39.77 ml`
- `wrong_label_for_value` | expected: `1 LVLs A4C 7.18 cm` | actual: `7.18 cm`

### 98667422_0042.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0042.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVLd A2C 6.64 cm`
- `LVEDV MOD A2C 92.50 ml`

#### Predicted output
- `1 LVLd A2C`
- `6.64 cm`
- `LVEDV MOD A2C 92.50 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 254, 65] ocr_bbox=(0, 18, 254, 51) confidence=0.9977

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0042.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVLd A2C 6.64 cm` | actual: `6.64 cm`

### 98667422_0043.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0043.dcm`
- Labels: 7
- Full matches: 1
- Value matches: 7
- Name matches: 1
- ROI detected: True

#### Expected lines
- `EF Biplane 31.77 %`
- `LVEDV MOD BP 111.96 ml`
- `LVESV MOD BP 76.40 ml`
- `LVEF MOD A2C 26.72 %`
- `SV MOD A2C 24.72 ml`
- `LVLs A2C 6.45 cm`
- `LVESV MOD A2C 67.79 ml`

#### Predicted output
- `EF Biplane`
- `31.77 %`
- `LVEDV MOD BP 111.96 ml`
- `LVESV MOD BP`
- `76.40 ml`
- `LVEF MOD A2C`
- `26.72 %`
- `SV MOD A2C`
- `24.72 ml`
- `1 LVLs A2C`
- `6.45 cm`
- `LVESV MOD A2C`
- `67.79 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 253, 177] ocr_bbox=(0, 18, 253, 163) confidence=0.9779

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0043.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `EF Biplane 31.77 %` | actual: `31.77 %`
- `wrong_label_for_value` | expected: `LVESV MOD BP 76.40 ml` | actual: `76.40 ml`
- `wrong_label_for_value` | expected: `LVEF MOD A2C 26.72 %` | actual: `26.72 %`
- `wrong_label_for_value` | expected: `SV MOD A2C 24.72 ml` | actual: `24.72 ml`
- `wrong_label_for_value` | expected: `LVLs A2C 6.45 cm` | actual: `6.45 cm`
- `wrong_label_for_value` | expected: `LVESV MOD A2C 67.79 ml` | actual: `67.79 ml`

### 98667422_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0046.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `MV E Vel 1.1 m/s`
- `MV DecT 172 ms`
- `MV Dec Slope 6 m/s`
- `MV A Vel 0.8 m/s`
- `MV E/A Ratio 1.4`

#### Predicted output
- `1 MV E Vel`
- `1.1 \, \mathrm{m/s}`
- `MV DecT`
- `172 ms`
- `MV Dec Slope 6 m/s2`
- `MV A Vel`
- `0.8 \,\mathrm{m/s}`
- `MV E/A Ratio`
- `1.4`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 212, 132] ocr_bbox=(0, 18, 212, 118) confidence=0.9697

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0046.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `MV E Vel 1.1 m/s` | actual: `1.1 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV DecT 172 ms` | actual: `172 ms`
- `wrong_label_for_value` | expected: `MV A Vel 0.8 m/s` | actual: `0.8 \.\mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV E/A Ratio 1.4` | actual: `1.4`

### 98667422_0052.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0052.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TAPSE 0.535 cm`

#### Predicted output
- `1 TAPSE 0.535 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 175, 44] ocr_bbox=(0, 18, 175, 30) confidence=0.8800

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0052.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0054.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0054.dcm`
- Labels: 12
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines
- `v 0.38 m/s`
- `p 0.57 mmHg`
- `AV Vmax 1.2 m/s`
- `AV Vmean 0.8 m/s`
- `AV maxPG 6 mmHg`
- `AV meanPG 3 mmHg`
- `AV VTI 20.3 cm`
- `1 AV Vmax 1.6 m/s`
- `AV Vmean 1.0 m/s`
- `AV maxPG 10 mmHg`
- `AV meanPG 5 mmHg`
- `AV VTI 30.0 cm`

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- frame=0 present=False bbox=None ocr_bbox=None confidence=0.0000

#### ROI visualizations
- none

#### Mismatches
- `missing_prediction` | expected: `v 0.38 m/s` | actual: `NOT FOUND`
- `missing_prediction` | expected: `p 0.57 mmHg` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV Vmax 1.2 m/s` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV Vmean 0.8 m/s` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV maxPG 6 mmHg` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV meanPG 3 mmHg` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV VTI 20.3 cm` | actual: `NOT FOUND`
- `missing_prediction` | expected: `1 AV Vmax 1.6 m/s` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV Vmean 1.0 m/s` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV maxPG 10 mmHg` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV meanPG 5 mmHg` | actual: `NOT FOUND`
- `missing_prediction` | expected: `AV VTI 30.0 cm` | actual: `NOT FOUND`

### 98667422_0065.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0065.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `IVC 2.9 cm`

#### Predicted output
- `1 IVC 2.9 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 123, 44] ocr_bbox=(0, 18, 123, 30) confidence=0.8701

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0065.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0066.dcm`
- Labels: 2
- Full matches: 0
- Value matches: 2
- Name matches: 0
- ROI detected: True

#### Expected lines
- `2 L 1.81 cm`
- `1 L 3.00 cm`

#### Predicted output
- `2 L 1.81 cm`
- `1 L 3.00 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 116, 66] ocr_bbox=(0, 18, 116, 52) confidence=0.9272

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0066.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `2 L 1.81 cm` | actual: `2 l 1.81 cm`
- `wrong_label_for_value` | expected: `1 L 3.00 cm` | actual: `1 l 3.00 cm`

### 98667422_0069.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0069.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 Ao Arch Diam 2.7 cm`

#### Predicted output
- `1 Ao Arch Diam 2.7 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 213, 43] ocr_bbox=(0, 18, 213, 29) confidence=0.9066

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0069.dcm__frame_000.png`

#### Mismatches
- none

### 98667422_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0075.dcm`
- Labels: 5
- Full matches: 0
- Value matches: 5
- Name matches: 0
- ROI detected: True

#### Expected lines
- `AVA Vmax 2.6 cm`
- `AVA (VTI) 2.4 cm`
- `1 LVOT Vmax 1.3 m/s`
- `LVOT maxPG 6.8 mmHg`
- `LVOT VTI 22.5 cm`

#### Predicted output
- `AVA Vmax`
- `2.6 cm2`
- `AVA (VTI)`
- `2.4 cm2`
- `1.3 \, \mathrm{m/s}`
- `1 LVOT Vmax`
- `LVOT maxPG`
- `6.8 mmHa`
- `LVOT VTI`
- `22.5 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 238, 132] ocr_bbox=(0, 18, 238, 118) confidence=0.9709

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0075.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `AVA Vmax 2.6 cm` | actual: `2.6 cm2`
- `wrong_label_for_value` | expected: `AVA (VTI) 2.4 cm` | actual: `2.4 cm2`
- `wrong_label_for_value` | expected: `1 LVOT Vmax 1.3 m/s` | actual: `1.3 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `LVOT maxPG 6.8 mmHg` | actual: `6.8 mmha`
- `wrong_label_for_value` | expected: `LVOT VTI 22.5 cm` | actual: `22.5 cm`

### 98667422_0076.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0076.dcm`
- Labels: 7
- Full matches: 0
- Value matches: 7
- Name matches: 0
- ROI detected: True

#### Expected lines
- `Vmax 0.91 m/s`
- `Vmean 0.65 m/s`
- `Pmax 3.30 mmHg`
- `Pmean 1.94 mmHg`
- `Env.Ti 256.92 m/s`
- `VTI 16.62 cm`
- `HR 226.67 BPM`

#### Predicted output
- `0.91 \, \mathrm{m/s}`
- `ı Vmax`
- `0.65 \, \mathrm{m/s}`
- `Vmean`
- `3.30 mmHg`
- `Pmax`
- `1.94 mmHg`
- `Pmean`
- `256.92 ms`
- `Env.Ti`
- `\mathbf{V}_{\mathbf{I}}`
- `16.62 cm`
- `226.67 BPM`
- `HR`

#### ROI frames
- frame=0 present=True bbox=[0, 20, 173, 155] ocr_bbox=(0, 34, 173, 141) confidence=0.9827

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/98667422_0076.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `Vmax 0.91 m/s` | actual: `0.91 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `Vmean 0.65 m/s` | actual: `0.65 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `Pmax 3.30 mmHg` | actual: `3.30 mmhg`
- `wrong_label_for_value` | expected: `Pmean 1.94 mmHg` | actual: `1.94 mmhg`
- `wrong_label_for_value` | expected: `Env.Ti 256.92 m/s` | actual: `256.92 ms`
- `wrong_label_for_value` | expected: `VTI 16.62 cm` | actual: `16.62 cm`
- `wrong_label_for_value` | expected: `HR 226.67 BPM` | actual: `226.67 bpm`

### 99094104_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 Ao Diam 3.2 cm`

#### Predicted output
- `1 Ao Diam 3.2 cm`
- `. .`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 41] ocr_bbox=(0, 19, 162, 27) confidence=0.8960

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0008.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0009.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0009.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 LVOT Diam 2.0 cm`

#### Predicted output
- `1 LVOT Diam 2.0 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 184, 42] ocr_bbox=(0, 18, 184, 28) confidence=0.8785

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0009.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0010.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0010.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 Ao asc 3.1 cm`

#### Predicted output
- `1 Ao asc 3.1 cm`
- `. .`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 150, 43] ocr_bbox=(0, 17, 150, 29) confidence=0.8760

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0010.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 LA Diam 4.6 cm`

#### Predicted output
- `1 LA Diam 4.6 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 41] ocr_bbox=(0, 19, 162, 27) confidence=0.8964

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0011.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0014.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `IVSd 0.7 cm`
- `LVIDd 5.7 cm`
- `LVPWd 0.9 cm`

#### Predicted output
- `1 IVSd`
- `0.7 cm`
- `LVIDd`
- `5.7 cm`
- `LVPWd 0.9 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 153, 85] ocr_bbox=(0, 17, 153, 71) confidence=0.9496

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0014.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `IVSd 0.7 cm` | actual: `0.7 cm`
- `wrong_label_for_value` | expected: `LVIDd 5.7 cm` | actual: `5.7 cm`

### 99094104_0015.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0015.dcm`
- Labels: 3
- Full matches: 1
- Value matches: 3
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVIDs 4.6 cm`
- `EF (Teich) 38 %`
- `%FS 18 %`

#### Predicted output
- `1 LVIDs`
- `4.6 cm`
- `EF(Teich) 38 %`
- `%FS`
- `18 %`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 154, 85] ocr_bbox=(0, 17, 154, 71) confidence=0.9499

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0015.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVIDs 4.6 cm` | actual: `4.6 cm`
- `wrong_label_for_value` | expected: `%FS 18 %` | actual: `18 %`

### 99094104_0018.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0018.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.7 m/s`
- `TR maxPG 29 mmHg`

#### Predicted output
- `2.7 m/s`
- `1 TR Vmax`
- `TR maxPG 29 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0018.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.7 m/s` | actual: `2.7 m/s`

### 99094104_0021.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0021.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `PRend Vmax 1.08 m/s`
- `PRend PG 4.69 mmHg`

#### Predicted output
- `1 PRend Vmax 1.08 m/s`
- `PRend PG 4.69 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 215, 63] ocr_bbox=(0, 17, 215, 49) confidence=0.9339

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0021.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0023.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0023.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `PRend Vmax 1.25 m/s`
- `PRend PG 6.24 mmHg`

#### Predicted output
- `1 PRend Vmax 1.25 m/s`
- `PRend PG 6.24 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 215, 63] ocr_bbox=(0, 17, 215, 49) confidence=0.9339

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0023.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0028.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0028.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 TR Vmax 2.8 m/s`
- `TR maxPG 31 mmHg`

#### Predicted output
- `2.8 \,\mathrm{m/s}`
- `1 TR Vmax`
- `TR maxPG 31 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0028.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `1 TR Vmax 2.8 m/s` | actual: `2.8 \.\mathrm{m/s}`

### 99094104_0042.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0042.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 LVLd A4C 8.83 cm`
- `LVEDV MOD A4C 123.64 ml`

#### Predicted output
- `1 LVLd A4C`
- `8.83 cm`
- `LVEDV MOD A4C 123.64 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 256, 63] ocr_bbox=(0, 17, 256, 49) confidence=0.9399

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0042.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `1 LVLd A4C 8.83 cm` | actual: `8.83 cm`

### 99094104_0043.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0043.dcm`
- Labels: 4
- Full matches: 1
- Value matches: 4
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LVEF MOD A4C 40.63 %`
- `SV MOD A4C 50.24 ml`
- `1 LVLs A4C 8.12 cm`
- `LVESV MOD A4C 73.40 ml`

#### Predicted output
- `LVEF MOD A4C`
- `40.63\ \%`
- `SV MOD A4C`
- `50.24 ml`
- `8.12 cm`
- `1 LVLs A4C`
- `LVESV MOD A4C \, 73.40 ml \,`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 245, 105] ocr_bbox=(0, 19, 245, 91) confidence=0.9730

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0043.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LVEF MOD A4C 40.63 %` | actual: `40.63\ \%`
- `wrong_label_for_value` | expected: `SV MOD A4C 50.24 ml` | actual: `50.24 ml`
- `wrong_label_for_value` | expected: `1 LVLs A4C 8.12 cm` | actual: `8.12 cm`

### 99094104_0044.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0044.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 LVLd A2C 9.27 cm`
- `LVEDV MOD A2C 156.99 ml`

#### Predicted output
- `1 LVLd A2C`
- `9.27 cm`
- `LVEDV MOD A2C 156.99 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 256, 63] ocr_bbox=(0, 17, 256, 49) confidence=0.9399

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0044.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `1 LVLd A2C 9.27 cm` | actual: `9.27 cm`

### 99094104_0045.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0045.dcm`
- Labels: 7
- Full matches: 1
- Value matches: 7
- Name matches: 1
- ROI detected: True

#### Expected lines
- `EF Biplane 43 %`
- `LVEDV MOD BP 142 ml`
- `LVESV MOD BP 81 ml`
- `LVEF MOD A2C 42.59 %`
- `SV MOD A2C 66.86 ml`
- `1 LVLs A2C 8.07 cm`
- `LVESV MOD A2C 90.12 ml`

#### Predicted output
- `EF Biplane`
- `43 %`
- `LVEDV MOD BP`
- `142 ml`
- `LVESV MOD BP`
- `81 mi`
- `LVEF MOD A2C`
- `42.59 %`
- `SV MOD A2C`
- `66.86 ml`
- `1 LVLs A2C`
- `8.07 cm`
- `LVESV MOD A2C 90.12 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 245, 170] ocr_bbox=(0, 19, 245, 156) confidence=0.9833

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0045.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `EF Biplane 43 %` | actual: `43 %`
- `wrong_label_for_value` | expected: `LVEDV MOD BP 142 ml` | actual: `142 ml`
- `wrong_label_for_value` | expected: `LVESV MOD BP 81 ml` | actual: `81 mi`
- `wrong_label_for_value` | expected: `LVEF MOD A2C 42.59 %` | actual: `42.59 %`
- `wrong_label_for_value` | expected: `SV MOD A2C 66.86 ml` | actual: `66.86 ml`
- `wrong_label_for_value` | expected: `1 LVLs A2C 8.07 cm` | actual: `8.07 cm`

### 99094104_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0046.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 2
- ROI detected: True

#### Expected lines
- `LALs A4C 7.0 cm`
- `LAAs A4C 25.3 cm`
- `LAESV A-L A4C 78 ml`

#### Predicted output
- `1 LALS A4C`
- `7.0 cm`
- `LAAs A4C 25.3 cm2`
- `LAESV A-L A4C 78 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 211, 84] ocr_bbox=(0, 18, 211, 70) confidence=0.9533

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0046.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LALs A4C 7.0 cm` | actual: `7.0 cm`

### 99094104_0047.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0047.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: True

#### Expected lines
- `2 RA LENGTH 6.7 cm`
- `1 LA LENGTH 7.1 cm`

#### Predicted output
- `2 RA LENGTH 6.7 cm`
- `1 LA LENGTH 7.1 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 189, 62] ocr_bbox=(0, 19, 189, 48) confidence=0.9491

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0047.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0051.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `MV E Vel 0.9 m/s`
- `MV DecT 239 ms`
- `MV Dec Slope 4 m/s`
- `MV A Vel 1.1 m/s`
- `MV E/A Ratio 0.8`

#### Predicted output
- `1 MV E Vel`
- `0.9 \, \mathrm{m/s}`
- `MV Decl`
- `239 ms`
- `MV Dec Slope 4 m/s2`
- `MV A Vel`
- `1.1 m/s`
- `MV E/A Ratio`
- `0.8`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 206, 127] ocr_bbox=(0, 17, 206, 113) confidence=0.9645

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0051.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `MV E Vel 0.9 m/s` | actual: `0.9 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `MV DecT 239 ms` | actual: `239 ms`
- `wrong_label_for_value` | expected: `MV A Vel 1.1 m/s` | actual: `1.1 m/s`
- `wrong_label_for_value` | expected: `MV E/A Ratio 0.8` | actual: `0.8`

### 99094104_0052.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0052.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `E' Lat 0.05 m/s`

#### Predicted output
- `1 E' Lat 0.05 m/s`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 154, 43] ocr_bbox=(0, 17, 154, 29) confidence=0.8766

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0052.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0053.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0053.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `E' Sept 0.05 m/s`

#### Predicted output
- `1 E' Sept 0.05 m/s`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 165, 42] ocr_bbox=(0, 18, 165, 28) confidence=0.8762

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0053.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0056.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0056.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `RVIDd 5.3 cm`

#### Predicted output
- `1 RVIDd 5.3 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 142, 41] ocr_bbox=(0, 19, 142, 27) confidence=0.8918

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0056.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0057.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0057.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 RVIDd 1.69 cm`

#### Predicted output
- `1 RVIDd 1.69 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 152, 41] ocr_bbox=(0, 19, 152, 27) confidence=0.8902

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0057.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0059.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0059.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.4 m/s`
- `TR maxPG 23 mmHg`

#### Predicted output
- `1 TR Vmax`
- `2.4 m/s`
- `TR maxPG 23 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0059.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.4 m/s` | actual: `2.4 m/s`

### 99094104_0060.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0060.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `TR Vmax 2.4 m/s`
- `TR maxPG 23 mmHg`

#### Predicted output
- `1 TR Vmax`
- `2.4 m/s`
- `TR maxPG 23 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0060.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `TR Vmax 2.4 m/s` | actual: `2.4 m/s`

### 99094104_0065.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0065.dcm`
- Labels: 5
- Full matches: 0
- Value matches: 5
- Name matches: 2
- ROI detected: True

#### Expected lines
- `AV Vmax 1.4 m/s`
- `AV Vmean 1.0 m/s`
- `AV maxPG 8 mmHg`
- `AV meanPG 4 mmHg`
- `AV VTI 33 cm`

#### Predicted output
- `1 AV Vmax`
- `1.4 m/s`
- `AV Vmean`
- `1.0 \, \text{m/s}`
- `AV maxPG`
- `8 mmHa`
- `AV meanPG 4 mmHq`
- `AV VTI`
- `33 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 204, 126] ocr_bbox=(0, 18, 204, 112) confidence=0.9687

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0065.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `AV Vmax 1.4 m/s` | actual: `1.4 m/s`
- `partial_mismatch` | expected: `AV Vmean 1.0 m/s` | actual: `1.0 \. \text{m/s}`
- `wrong_label_for_value` | expected: `AV maxPG 8 mmHg` | actual: `8 mmha`
- `wrong_unit` | expected: `AV meanPG 4 mmHg` | actual: `av meanpg 4 mmhq`
- `wrong_label_for_value` | expected: `AV VTI 33 cm` | actual: `33 cm`

### 99094104_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0066.dcm`
- Labels: 5
- Full matches: 0
- Value matches: 5
- Name matches: 0
- ROI detected: True

#### Expected lines
- `AVA Vmax 1.9 cm`
- `AVA (VTI) 1.8 cm`
- `1 LVOT Vmax 0.9 m/s`
- `LVOT maxPG 3 mmHg`
- `LVOT VTI 19.4 cm`

#### Predicted output
- `AVA Vmax`
- `1.9 cm2`
- `1.8 cm2`
- `AVA (VTI)`
- `1 LVOT Vmax`
- `0.9 \, \mathrm{m/s}`
- `LVOT maxPG`
- `3 mmHg`
- `LVOT VTI`
- `19.4 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 4, 215, 127] ocr_bbox=(0, 18, 215, 113) confidence=0.9693

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0066.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `AVA Vmax 1.9 cm` | actual: `1.9 cm2`
- `wrong_label_for_value` | expected: `AVA (VTI) 1.8 cm` | actual: `1.8 cm2`
- `wrong_label_for_value` | expected: `1 LVOT Vmax 0.9 m/s` | actual: `0.9 \. \mathrm{m/s}`
- `wrong_label_for_value` | expected: `LVOT maxPG 3 mmHg` | actual: `3 mmhg`
- `wrong_label_for_value` | expected: `LVOT VTI 19.4 cm` | actual: `19.4 cm`

### 99094104_0068.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0068.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 5
- Name matches: 1
- ROI detected: True

#### Expected lines
- `LAESV (A-L) 93.18 ml`
- `LAESV Index (A-L) 56.13 ml/m2`
- `LALs A2C 7.1 cm`
- `LAAs A2C 30 cm`
- `LAESV A-L A2C 109.7 ml`

#### Predicted output
- `LAESV(A-L)`
- `93.18 ml`
- `LAESV Index (A-L) 56.13 ml/m2`
- `1 LALS A2C`
- `7.1 cm`
- `LAAs A2C`
- `30 cm2`
- `LAESV A-L A2C`
- `109.7 ml`

#### ROI frames
- frame=0 present=True bbox=[0, 3, 289, 128] ocr_bbox=(0, 17, 289, 114) confidence=0.9679

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0068.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `LAESV (A-L) 93.18 ml` | actual: `93.18 ml`
- `wrong_label_for_value` | expected: `LALs A2C 7.1 cm` | actual: `7.1 cm`
- `wrong_label_for_value` | expected: `LAAs A2C 30 cm` | actual: `30 cm2`
- `wrong_label_for_value` | expected: `LAESV A-L A2C 109.7 ml` | actual: `109.7 ml`

### 99094104_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0074.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 TR Vmax 2.6 m/s`
- `TR maxPG 28 mmHg`

#### Predicted output
- `2.6 \,\mathrm{m/s}`
- `1 TR Vmax`
- `TR maxPG 28 mmHg`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 203, 61] ocr_bbox=(0, 19, 203, 47) confidence=0.9507

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0074.dcm__frame_000.png`

#### Mismatches
- `wrong_label_for_value` | expected: `1 TR Vmax 2.6 m/s` | actual: `2.6 \.\mathrm{m/s}`

### 99094104_0079.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0079.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 IVC 2.1 cm`

#### Predicted output
- `1 IVC 2.1 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 119, 41] ocr_bbox=(0, 19, 119, 27) confidence=0.8862

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0079.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0087.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0087.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `1 Ao Arch Diam 2.6 cm`

#### Predicted output
- `1 Ao Arch Diam 2.6 cm`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 206, 41] ocr_bbox=(0, 19, 206, 27) confidence=0.9033

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0087.dcm__frame_000.png`

#### Mismatches
- none

### 99094104_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: True

#### Expected lines
- `Ao Diam 3.2 cm`

#### Predicted output
- `1 Ao Diam 3.2 cm`
- `. .`

#### ROI frames
- frame=0 present=True bbox=[0, 5, 162, 41] ocr_bbox=(0, 19, 162, 27) confidence=0.8960

#### ROI visualizations
- `roi_visualizations/validation_labels/surya/raw_no_parser/99094104_0008.dcm__frame_000.png`

#### Mismatches
- none

## validation_labels / surya / regex_parser

### 92290733_0003.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0003.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0004.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0004.dcm`
- Labels: 4
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0007.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0007.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0010.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0010.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0014.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0019.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0019.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0030.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0030.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0032.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0032.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0033.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0033.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0035.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0035.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0040.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0040.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0045.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0045.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0046.dcm`
- Labels: 7
- Full matches: 4
- Value matches: 6
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0051.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0071.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0071.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0072.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0072.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0073.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0073.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0074.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0075.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0076.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0076.dcm`
- Labels: 9
- Full matches: 4
- Value matches: 7
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0077.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0077.dcm`
- Labels: 6
- Full matches: 4
- Value matches: 6
- Name matches: 6
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0078.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0078.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 1
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0079.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0079.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0002.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0002.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0005.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0005.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0006.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0006.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0007.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0007.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0008.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0014.dcm`
- Labels: 2
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0025.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0025.dcm`
- Labels: 2
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0036.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0036.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0037.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0037.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0038.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0038.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0039.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0039.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 4
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0040.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0040.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0041.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0041.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0042.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0042.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0043.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0043.dcm`
- Labels: 7
- Full matches: 7
- Value matches: 7
- Name matches: 7
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0046.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0052.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0052.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0054.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0054.dcm`
- Labels: 12
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0065.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0065.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0066.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0069.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0069.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0075.dcm`
- Labels: 5
- Full matches: 1
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0076.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0076.dcm`
- Labels: 7
- Full matches: 0
- Value matches: 5
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0009.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0009.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0010.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0010.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0014.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0015.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0015.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0018.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0018.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0021.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0021.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0023.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0023.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0028.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0028.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0042.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0042.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0043.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0043.dcm`
- Labels: 4
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0044.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0044.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0045.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0045.dcm`
- Labels: 7
- Full matches: 6
- Value matches: 6
- Name matches: 6
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0046.dcm`
- Labels: 3
- Full matches: 2
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0047.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0047.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0051.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0052.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0052.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0053.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0053.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0056.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0056.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0057.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0057.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0059.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0059.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0060.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0060.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0065.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0065.dcm`
- Labels: 5
- Full matches: 3
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0066.dcm`
- Labels: 5
- Full matches: 2
- Value matches: 4
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0068.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0068.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0074.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0079.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0079.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0087.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0087.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

## validation_labels / surya / local_llm_parser

### 92290733_0003.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0003.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0004.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0004.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0007.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0007.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0010.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0010.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0014.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0019.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0019.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0030.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0030.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0032.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0032.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0033.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0033.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0035.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0035.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0040.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0040.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0045.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0045.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0046.dcm`
- Labels: 7
- Full matches: 4
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0051.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0071.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0071.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0072.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0072.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0073.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0073.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0074.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0075.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0076.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0076.dcm`
- Labels: 9
- Full matches: 2
- Value matches: 8
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0077.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0077.dcm`
- Labels: 6
- Full matches: 6
- Value matches: 6
- Name matches: 6
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0078.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0078.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 1
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 92290733_0079.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s92290733/92290733_0079.dcm`
- Labels: 1
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0002.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0002.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0005.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0005.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0006.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0006.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0007.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0007.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0008.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0014.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0025.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0025.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0036.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0036.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0037.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0037.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0038.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0038.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0039.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0039.dcm`
- Labels: 5
- Full matches: 5
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0040.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0040.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0041.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0041.dcm`
- Labels: 4
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0042.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0042.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0043.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0043.dcm`
- Labels: 7
- Full matches: 4
- Value matches: 7
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0046.dcm`
- Labels: 5
- Full matches: 5
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0052.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0052.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0054.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0054.dcm`
- Labels: 12
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0065.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0065.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0066.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0069.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0069.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0075.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0075.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 98667422_0076.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s98667422/98667422_0076.dcm`
- Labels: 7
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0009.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0009.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0010.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0010.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0011.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0011.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0014.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0014.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0015.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0015.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0018.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0018.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0021.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0021.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0023.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0023.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0028.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0028.dcm`
- Labels: 2
- Full matches: 1
- Value matches: 2
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0042.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0042.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0043.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0043.dcm`
- Labels: 4
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0044.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0044.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0045.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0045.dcm`
- Labels: 7
- Full matches: 6
- Value matches: 6
- Name matches: 6
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0046.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0046.dcm`
- Labels: 3
- Full matches: 3
- Value matches: 3
- Name matches: 3
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0047.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0047.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0051.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0051.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 5
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0052.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0052.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0053.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0053.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0056.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0056.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0057.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0057.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0059.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0059.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0060.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0060.dcm`
- Labels: 2
- Full matches: 2
- Value matches: 2
- Name matches: 2
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0065.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0065.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0066.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0066.dcm`
- Labels: 5
- Full matches: 4
- Value matches: 4
- Name matches: 4
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0068.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0068.dcm`
- Labels: 5
- Full matches: 5
- Value matches: 5
- Name matches: 5
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0074.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0074.dcm`
- Labels: 2
- Full matches: 0
- Value matches: 0
- Name matches: 0
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0079.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0079.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0087.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0087.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

### 99094104_0008.dcm

- File: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10002430/s99094104/99094104_0008.dcm`
- Labels: 1
- Full matches: 1
- Value matches: 1
- Name matches: 1
- ROI detected: False

#### Expected lines

#### Predicted output
- `NO PREDICTIONS`

#### ROI frames
- none

#### ROI visualizations
- none

#### Mismatches
- none

