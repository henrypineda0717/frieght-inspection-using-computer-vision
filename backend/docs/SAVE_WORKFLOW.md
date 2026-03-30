# Analysis Save Workflow

## Overview

The system now supports a two-step workflow:
1. **Analyze**: Run detection and OCR, show results to user
2. **Save**: User reviews/edits results, then explicitly saves to database

This allows users to correct any OCR errors or detection mistakes before persisting to the database.

## API Endpoints

### 1. Analyze Image (Without Auto-Save)

**Endpoint**: `POST /api/analyze/`

**Parameters**:
- `image`: Image file (required)
- `auto_save`: Boolean (default: `false`) - Set to `true` to auto-save
- `damage_sensitivity`: String (default: "medium")
- `inspection_stage`: String (optional) - "pre" or "post"
- `use_multimodel`: Boolean (default: `true`)

**Response**: Analysis results with detections, container ID, etc.

**Example**:
```javascript
const formData = new FormData();
formData.append('image', imageFile);
formData.append('auto_save', 'false');  // Don't save automatically

const response = await fetch('/api/analyze/', {
  method: 'POST',
  body: formData
});

const analysisResults = await response.json();
// Display results to user for review/editing
```

### 2. Save Edited Analysis

**Endpoint**: `POST /api/analyze/save-analysis`

**Parameters**:
- `image`: Original image file (required)
- `analysis_data`: JSON string with edited analysis results (required)

**Response**:
```json
{
  "success": true,
  "inspection_id": 123,
  "message": "Analysis saved successfully"
}
```

**Example**:
```javascript
// User has edited the results
const editedResults = {
  container_id: "MSCU1234567",  // User corrected from "UNKNOWN"
  container_type: "45R1",
  status: "alert",
  detections: [...],
  // ... other fields
};

const formData = new FormData();
formData.append('image', originalImageFile);
formData.append('analysis_data', JSON.stringify(editedResults));

const response = await fetch('/api/analyze/save-analysis', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(`Saved with ID: ${result.inspection_id}`);
```

### 3. Generate Report (Without Saving)

**Endpoint**: `POST /api/analyze/generate-report`

**Parameters**:
- `analysis_data`: JSON string with analysis results (required)
- `image`: Image file (optional)

**Response**: PDF file download

**Example**:
```javascript
const formData = new FormData();
formData.append('analysis_data', JSON.stringify(analysisResults));
formData.append('image', imageFile);

const response = await fetch('/api/analyze/generate-report', {
  method: 'POST',
  body: formData
});

const blob = await response.blob();
// Download PDF
```

## Frontend Workflow

### Recommended User Flow

1. **Upload Image**
   ```
   User uploads image → Frontend calls /api/analyze/ with auto_save=false
   ```

2. **Display Results**
   ```
   Frontend displays:
   - Container ID (editable text field)
   - Container Type (editable dropdown)
   - Detections list
   - Status indicators
   - Contamination level
   ```

3. **User Reviews & Edits**
   ```
   User can:
   - Correct container ID if OCR was wrong
   - Change container type
   - Adjust contamination level
   - Modify status
   - Add/remove detections
   ```

4. **Save or Generate Report**
   ```
   User clicks "Save" → Frontend calls /api/analyze/save-analysis
   OR
   User clicks "Download Report" → Frontend calls /api/analyze/generate-report
   ```

### Example Frontend Component (React)

```jsx
function AnalysisPage() {
  const [analysisResults, setAnalysisResults] = useState(null);
  const [editedResults, setEditedResults] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // Step 1: Analyze image
  const handleImageUpload = async (file) => {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('auto_save', 'false');
    
    const response = await fetch('/api/analyze/', {
      method: 'POST',
      body: formData
    });
    
    const results = await response.json();
    setAnalysisResults(results);
    setEditedResults(results); // Initialize editable copy
  };

  // Step 2: User edits results
  const handleContainerIdChange = (newId) => {
    setEditedResults({
      ...editedResults,
      container_id: newId
    });
  };

  // Step 3: Save to database
  const handleSave = async () => {
    setIsSaving(true);
    
    const formData = new FormData();
    formData.append('image', originalImageFile);
    formData.append('analysis_data', JSON.stringify(editedResults));
    
    const response = await fetch('/api/analyze/save-analysis', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    alert(`Saved successfully! Inspection ID: ${result.inspection_id}`);
    setIsSaving(false);
  };

  return (
    <div>
      <input type="file" onChange={(e) => handleImageUpload(e.target.files[0])} />
      
      {editedResults && (
        <div>
          <h2>Analysis Results</h2>
          
          <label>
            Container ID:
            <input
              value={editedResults.container_id}
              onChange={(e) => handleContainerIdChange(e.target.value)}
            />
          </label>
          
          {/* More editable fields... */}
          
          <button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save to Database'}
          </button>
        </div>
      )}
    </div>
  );
}
```

## Migration from Auto-Save

If your frontend currently auto-saves, you have two options:

### Option 1: Keep Auto-Save (Backward Compatible)
```javascript
// Set auto_save=true to maintain old behavior
formData.append('auto_save', 'true');
```

### Option 2: Implement Manual Save (Recommended)
```javascript
// Step 1: Analyze without saving
formData.append('auto_save', 'false');
const results = await analyzeImage(formData);

// Step 2: Show results to user, allow editing

// Step 3: Save when user clicks "Save"
await saveAnalysis(editedResults, imageFile);
```

## Benefits

1. **Data Quality**: Users can correct OCR errors before saving
2. **Flexibility**: Users can review and adjust all fields
3. **No Clutter**: Database only contains verified, correct data
4. **Audit Trail**: Clear distinction between analysis and saved records
5. **User Control**: Users decide what gets saved

## Database Impact

- **Before**: Every analysis automatically created a database record
- **After**: Only user-approved analyses are saved
- **Result**: Cleaner database with higher quality data

## Testing

### Test Manual Save Flow

```bash
# 1. Analyze without saving
curl -X POST http://localhost:8000/api/analyze/ \
  -F "image=@test_image.jpg" \
  -F "auto_save=false"

# 2. Save edited results
curl -X POST http://localhost:8000/api/analyze/save-analysis \
  -F "image=@test_image.jpg" \
  -F 'analysis_data={"container_id":"MSCU1234567","status":"ok",...}'
```

### Test Auto-Save (Legacy)

```bash
# Auto-save enabled
curl -X POST http://localhost:8000/api/analyze/ \
  -F "image=@test_image.jpg" \
  -F "auto_save=true"
```
