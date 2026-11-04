
import backgroundVideo from "../assets/background.mp4";

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

      <div className="home-content">
        <h1>Welcome Home</h1>
      </div>

    </div>
  );
}

export default Home;
