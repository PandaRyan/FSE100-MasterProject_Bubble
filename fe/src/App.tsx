
import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import FingerCounting from "./pages/FingerCounting";
import BubbleBlitzLevelSelect from "./pages/BubbleBlitzLevelSelect";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/digibubble" element={<FingerCounting />} />
      <Route path="/bubbleblitzlevelselect" element={<BubbleBlitzLevelSelect />} />
      <Route path="/bubbleblitzeasy" element={<Home />} /> //change ltr
      <Route path="/bubbleblitzmedium" element={<Home />} />
      <Route path="/bubbleblitzhard" element={<Home />} />
    </Routes>
  );
}

export default App;
