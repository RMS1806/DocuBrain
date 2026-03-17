import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom' // <--- Add this
import App from './app.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter> {/* Wrap App in BrowserRouter */}
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)