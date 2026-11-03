namespace VvvfSimulator
{
    // Deterministic stand-in for System.Random in the carrier's random modulation (xorshift32), mirrored in the JS port's test.
    public class DetRandom
    {
        public static uint Seed = 2463534242u;
        private uint x = Seed;
        public double NextDouble()
        {
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            return x / 4294967296.0;
        }
    }
}
namespace VvvfSimulator.Generation.Audio.TrainSound
{
    public class AudioResourceManager
    {
        public static string SampleIrPath { get; set; } = "";
        public static void ReadResourceAudioFileSample(string path, out float[] Response, out int SampleRate) { Response = []; SampleRate = -1; }
        public static float[] Resample(float[] Input, int SampleRate, int ResampleRate) => Input;
    }
}
