
import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import FingerCounting from "./pages/FingerCounting";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/digibubble" element={<FingerCounting />} />
    </Routes>
  );
}

export default App;
