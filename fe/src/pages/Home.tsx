import { Link } from "react-router-dom";
import "../home.css";
import backgroundVideo from "../assets/background.mp4";
import bubbleBlitzBtn from "../assets/bubbleblitzbtn.png";
import digiBubbleBtn from "../assets/digibubblebtn.png";

function Home() {
  return (
    <div className="home-screen">
      <video
        className="background-video"
        src={backgroundVideo}
        autoPlay
        loop
        muted
        playsInline
      />

      <div className="button-container">
        <Link to="/digibubble">
          <img src={digiBubbleBtn} alt="Play DigiBubble" className="game-btn digi-btn" />
        </Link>

        <Link to="#">
          <img src={bubbleBlitzBtn} alt="Play Bubble Blitz" className="game-btn blitz-btn" />
        </Link>
      </div>
    </div>
  );
}

export default Home;