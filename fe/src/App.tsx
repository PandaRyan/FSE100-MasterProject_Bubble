
import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import About from "./pages/About";
import FingerCounting from "./pages/FingerCounting";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/about" element={<About />} />
      <Route path="/fingercounting" element={<FingerCounting />} />
    </Routes>
  );
}

export default App;
