# ISO 6346 Container ID Implementation

## Overview

This document describes the implementation of ISO 6346 container identification standard in the container inspection system.

## ISO 6346 Standard

The ISO 6346 standard defines the format for shipping container identification:

```
AAAU123456C
│││││││││││
│││└┴┴┴┴┴┴┴─ 6-digit serial number + 1 check digit
││└───────── Category identifier (U=freight, J=detachable, Z=trailer)
└┴────────── 3-letter owner code (e.g., MSK=Maersk, MSC=Mediterranean Shipping)
```

### Format Breakdown

1. **Owner Code** (3 letters): Identifies the container owner/operator
   - Examples: MSK (Maersk), MSC (Mediterranean Shipping), CMA (CMA CGM)

2. **Category Identifier** (1 letter): Equipment category
   - U: Freight container
   - J: Detachable freight container equipment
   - Z: Trailer and chassis

3. **Serial Number** (6 digits): Unique identifier assigned by owner

4. **Check Digit** (1 digit): Validation digit calculated using ISO 6346 algorithm

### Check Digit Calculation

The check digit is calculated using the following algorithm:

1. Convert each character to its numeric value:
   - A=10, B=12, C=13, ..., Z=36 (skip 11)
   - Digits remain as their numeric value

2. Multiply each value by 2^position (position 0-9)

3. Sum all products

4. Calculate: `check_digit = sum % 11`

5. If result is 10, check digit is 0

## Implementation

### OCR Processor Updates

**File**: `backend/app/services/ocr_processor.py`

- Updated regex pattern to match ISO 6346 format: `[A-Z]{3}[UJZ]\d{7}`
- Added character-to-value mapping for check digit calculation
- Implemented `_calculate_check_digit()` method
- Enhanced `_validate_container_id()` to verify check digits
- Added logging for invalid check digits

### Database Schema Updates

**File**: `backend/app/models/container.py`

Added new fields to Container model:
- `owner_code` (VARCHAR(3)): First 3 letters
- `category` (VARCHAR(1)): Category identifier (U/J/Z)
- `serial_number` (VARCHAR(6)): 6-digit serial
- `check_digit` (INTEGER): Validation digit

### Migration

**File**: `backend/migrations/migration_002_add_iso6346_fields.py`

- Adds new columns to containers table
- Parses existing container IDs to populate new fields
- Backward compatible with existing data

### Persistence Service Updates

**File**: `backend/app/services/persistence_service.py`

- Automatically parses container IDs when creating/updating containers
- Populates ISO 6346 fields (owner_code, category, serial_number, check_digit)
- Handles both valid IDs and "UNKNOWN" gracefully

### API Schema Updates

**File**: `backend/app/schemas/container.py`

Updated ContainerResponse to include:
- owner_code
- category
- serial_number
- check_digit

## Usage

### Running Migration

```bash
# Run standalone migration
python backend/migrations/migration_002_add_iso6346_fields.py

# Or run all migrations
python -m migrations.run_migrations upgrade
```

### Testing

```bash
# Run OCR processor tests
python -m pytest backend/tests/test_ocr_processor.py -v

# Test specific check digit validation
python -m pytest backend/tests/test_ocr_processor.py::TestOCRProcessor::test_calculate_check_digit -v
```

### Example Container IDs

Valid ISO 6346 container IDs:
- `MSCU1234560` - Maersk freight container
- `TEMU9876543` - TE freight container
- `ABCJ1234567` - ABC detachable equipment
- `XYZZ0000001` - XYZ trailer/chassis

Invalid formats:
- `ABCD1234567` - 4 letters (old format, not ISO 6346)
- `MSCA1234567` - Invalid category (A not in U/J/Z)
- `MSC1234567` - Only 2 letters (missing owner code letter)
- `MSCU123456` - Only 6 digits (missing check digit)

## Benefits

1. **Validation**: Check digit verification catches OCR errors
2. **Standardization**: Follows international shipping container standard
3. **Traceability**: Owner code enables tracking container ownership
4. **Data Quality**: Structured fields improve database queries and reporting

## Future Enhancements

1. **Owner Database**: Map owner codes to company names
2. **Type Detection**: Detect container type from ISO type code
3. **Validation Strictness**: Option to reject containers with invalid check digits
4. **Reporting**: Generate reports grouped by owner or category
