# Frontend - Container Inspection System

## Overview

Web-based user interface for container inspection analysis and history viewing.

## Structure

```
frontend/
├── pages/
│   ├── index.html      # Live analysis interface
│   └── history.html    # Inspection history viewer
└── assets/
    ├── css/
    │   └── style.css   # Styles
    ├── js/
    │   ├── main.js     # Main application logic
    │   └── ui.js       # UI components
    └── images/
        └── pti-logo.png
```

## Features

### Live Analysis Page (`index.html`)

- **Video/Image Upload**: Analyze containers from media files
- **Real-time Detection**: View YOLO detections with bounding boxes
- **Learning Mode**: Draw boxes to train custom models
- **Pre/Post Wash**: Compare inspection stages
- **Contamination Index**: Visual 1-9 scale
- **Settings**: Adjust sensitivity, spot detection, vision backend

### History Page (`history.html`)

- **Statistics Dashboard**: System-wide metrics
- **Inspection List**: Paginated table with search/filter
- **Detail View**: Complete inspection with all frames
- **Manual Override**: Correct OCR mistakes
- **Image Gallery**: View archived images with overlays

## Development

### Local Development

The frontend is served by the FastAPI backend:

```bash
# Start backend (from project root)
cd backend
uvicorn app.main:app --reload

# Access frontend
# Live Analysis: http://localhost:8000/
# History: http://localhost:8000/history.html
```

### File Structure

**HTML Files** (`pages/`)
- Self-contained pages with embedded CSS and JavaScript
- Responsive design for desktop use
- Dark theme optimized for industrial environments

**Assets** (`assets/`)
- `css/` - Stylesheets (if extracted from HTML)
- `js/` - JavaScript modules (if extracted from HTML)
- `images/` - Logo and icons

## API Integration

The frontend communicates with the backend API:

```javascript
const API_BASE = "http://localhost:8000";

// Analyze image
const formData = new FormData();
formData.append('image', imageFile);
const response = await fetch(`${API_BASE}/api/analyze/`, {
    method: 'POST',
    body: formData
});

// Get history
const history = await fetch(`${API_BASE}/api/history/?page=1`);
```

## Customization

### Branding

Update logo:
```
frontend/assets/images/pti-logo.png
```

### Colors

Edit CSS variables in `index.html` or `history.html`:

```css
:root {
  --bg-dark: #262626;
  --bg-darker: #1f1f1f;
  --bg-blackish: #181818;
  --gray-border: #3a3a3a;
  --gray-soft: #9ca3af;
}
```

### Features

Enable/disable features by modifying JavaScript:

```javascript
// Disable GPT features
const use_vision_gpt = false;
const use_text_gpt = false;
```

## Browser Support

- **Chrome/Edge**: ✅ Fully supported
- **Firefox**: ✅ Fully supported
- **Safari**: ✅ Supported (may need testing)
- **Mobile**: ⚠️ Desktop-optimized (mobile support planned)

## Performance

### Optimization Tips

1. **Image Upload**: Compress large images before upload
2. **Video Processing**: Use shorter videos or lower frame rates
3. **History Loading**: Use pagination (default: 20 items/page)
4. **Caching**: Browser caches static assets automatically

## Accessibility

### Current Status

- ✅ Keyboard navigation
- ✅ Semantic HTML
- ⚠️ Screen reader support (basic)
- ⚠️ ARIA labels (partial)

### Improvements Needed

- [ ] Complete ARIA labels
- [ ] Better keyboard shortcuts
- [ ] High contrast mode
- [ ] Screen reader testing

## Future Enhancements

### Planned Features

- [ ] Mobile-responsive design
- [ ] Progressive Web App (PWA)
- [ ] Offline support
- [ ] Real-time WebSocket updates
- [ ] Drag-and-drop file upload
- [ ] Batch processing interface
- [ ] Export reports to PDF
- [ ] Advanced filtering options

### Technical Improvements

- [ ] Extract CSS to separate files
- [ ] Modularize JavaScript
- [ ] Add build process (webpack/vite)
- [ ] Implement state management
- [ ] Add unit tests
- [ ] TypeScript migration

## Troubleshooting

### Images Not Loading

**Problem**: Images from history not displaying
**Solution**: Check backend is serving images correctly

```bash
curl http://localhost:8000/api/images/storage/inspections/...
```

### API Connection Failed

**Problem**: Cannot connect to backend
**Solution**: Verify backend is running and CORS is configured

```javascript
// Check API_BASE matches your backend URL
const API_BASE = "http://localhost:8000";
```

### Video Upload Fails

**Problem**: Video file too large
**Solution**: Check `MAX_UPLOAD_SIZE` in backend config

## Contributing

When modifying the frontend:

1. Test in multiple browsers
2. Verify mobile responsiveness
3. Check console for errors
4. Test with slow network (throttling)
5. Validate HTML/CSS
6. Update documentation

## Support

For frontend issues:
- Check browser console for errors
- Verify backend API is responding
- Test with different browsers
- Review network tab in DevTools
