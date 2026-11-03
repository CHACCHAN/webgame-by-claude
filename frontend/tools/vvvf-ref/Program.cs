using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using VvvfSimulator.Vvvf;
using VvvfSimulator.Vvvf.Calculation;
using static VvvfSimulator.Vvvf.Model.Struct;
using TA = VvvfSimulator.Data.TrainAudio.Struct;

// Reference runs of VVVF-Simulator's calculation (VvvfGeeks, non-GUI parts compiled as is) for checking the JS port.
// usage: RefSim <yaml> <out.f32> <train|line> <scenario.txt> <fs> <calcCount> [gear1 gear2] [seed]
// scenario lines: "<seconds> <P|N|B> <Hz per second>" (mascon: power / neutral / brake, base frequency change rate)
static class Program
{
    class Param { public double FrequencyChangeRate; public bool IsBraking; public bool IsFreeRunning; }

    // = Generation/Audio/RealTime.RealTimeFrequencyControl (copied: that file needs NAudio's Windows parts)
    static void RealTimeFrequencyControl(Domain Control, Param Param, double dt, VvvfSimulator.Data.Vvvf.Struct data)
    {
        Control.SetBraking(Param.IsBraking);
        Control.SetPowerOff(Param.IsFreeRunning);
        var baseWave = Control.GetBaseWaveInstance();
        double angleFrequency = baseWave.AngleFrequency;
        angleFrequency += Param.FrequencyChangeRate * dt;
        if (angleFrequency < 0) angleFrequency = 0;
        if (!Control.IsFreeRun())
        {
            if (Control.IsBaseWaveTimeChangeAllowed())
            {
                if (angleFrequency != 0)
                {
                    double amp = baseWave.AngleFrequency / angleFrequency;
                    baseWave.Time *= amp;
                }
            }
            baseWave.AngleFrequency = angleFrequency;
            Control.SetControlFrequency(baseWave.Frequency);
        }
        Control.ProcessControlParameter(dt, data.JerkSetting);
    }

    // = Generation/Audio/TrainSound/Audio.CalculateHarmonicSounds / CalculateTrainSound (copied)
    static double CalculateHarmonicSounds(Domain control, List<TA.HarmonicData> harmonics)
    {
        var baseWave = control.GetBaseWaveInstance();
        double sound = 0;
        for (int harmonic = 0; harmonic < harmonics.Count; harmonic++)
        {
            var harmonic_data = harmonics[harmonic];
            var amplitude_data = harmonic_data.Amplitude;
            if (harmonic_data.Range.Start > baseWave.Frequency) continue;
            if (harmonic_data.Range.End >= 0 && harmonic_data.Range.End < baseWave.Frequency) continue;
            double harmonic_freq = harmonic_data.Harmonic * baseWave.Frequency;
            if (harmonic_data.Disappear != -1 && harmonic_freq > harmonic_data.Disappear) continue;
            double sine_val = Math.Sin(baseWave.Time * baseWave.AngleFrequency * harmonic_data.Harmonic);
            double amplitude = amplitude_data.StartValue + (amplitude_data.EndValue - amplitude_data.StartValue) / (amplitude_data.End - harmonic_data.Amplitude.Start) * (baseWave.Frequency - harmonic_data.Amplitude.Start);
            if (amplitude > amplitude_data.MaximumValue) amplitude = amplitude_data.MaximumValue;
            if (amplitude < amplitude_data.MinimumValue) amplitude = amplitude_data.MinimumValue;
            double amplitude_disappear = (harmonic_freq + 100.0 > harmonic_data.Disappear) ? ((harmonic_data.Disappear - harmonic_freq) / 100.0) : 1;
            sine_val *= amplitude * (harmonic_data.Disappear == -1 ? 1 : amplitude_disappear);
            sound += sine_val;
        }
        return sound;
    }
    static double CalculateTrainSound(Domain Control, TA Data)
    {
        Common.CalculatePhsaseState(Control, 0);
        double motorPwmSound = Control.Motor.Parameter.DiffTe * Math.Pow(10, Data.MotorVolumeDb);
        double motorSound = CalculateHarmonicSounds(Control, Data.HarmonicSound);
        double gearSound = CalculateHarmonicSounds(Control, Data.GearSound);
        return (motorPwmSound + motorSound + gearSound) * Math.Pow(10, Data.TotalVolumeDb);
    }

    static int Main(string[] a)
    {
        CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        string yaml = a[0], outPath = a[1], mode = a[2], scen = a[3];
        int fs = int.Parse(a[4]), calc = int.Parse(a[5]);
        int g1 = a.Length > 7 ? int.Parse(a[6]) : 0, g2 = a.Length > 7 ? int.Parse(a[7]) : 0;
        if (a.Length > 8) VvvfSimulator.DetRandom.Seed = uint.Parse(a[8]);
        var data = VvvfSimulator.Data.Vvvf.Manager.Load(yaml, true)!;
        var train = new TA();
        if (g1 > 0) train.SetCalculatedGearHarmonic(g1, g2);
        var control = new Domain(train.MotorSpec);
        double dt = 1.0 / fs;
        var P = new Param();
        using var bw = new BinaryWriter(File.Create(outPath));
        using var tr = new StreamWriter(outPath + ".trace.csv");
        tr.WriteLine("t,base,control,freeRun,powerOff,braking,none,zero,amp,type,count,alt,carrier,Te,wr");
        double t = 0;
        foreach (var line in File.ReadAllLines(scen))
        {
            var p = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (p.Length < 3 || p[0].StartsWith("#")) continue;
            double sec = double.Parse(p[0]);
            int at = p[1] == "P" ? 1 : p[1] == "B" ? -1 : 0;
            double rate = double.Parse(p[2]);
            // = Controller Design1.SetState: neutral keeps the last braking flag
            P.FrequencyChangeRate = at * rate * Math.PI * 2;
            bool preBraking = P.IsBraking;
            P.IsFreeRunning = at == 0;
            P.IsBraking = at == 0 ? preBraking : at < 0;
            long blocks = (long)Math.Round(sec / (calc * dt));
            for (long b = 0; b < blocks; b++)
            {
                RealTimeFrequencyControl(control, P, calc * dt, data);
                VvvfSimulator.Data.Vvvf.Analyze.Calculate(control, data);
                var es = control.ElectricalState;
                string carrier = "";
                if (!es.IsNone && es.CarrierFrequency != null)
                    carrier = es.CarrierFrequency.BaseFrequency is ElectricalParameter.CarrierParameter.ConstantFrequency c ? c.Value.ToString("R") : "vib";
                tr.WriteLine(string.Join(",", new string[] {
                    t.ToString("R"), control.GetBaseWaveInstance().Frequency.ToString("R"), control.GetControlFrequency().ToString("R"),
                    control.IsFreeRun() ? "1" : "0", control.IsPowerOff() ? "1" : "0", control.IsBraking() ? "1" : "0",
                    es.IsNone ? "1" : "0", es.IsZeroOutput ? "1" : "0", (es.BaseWaveAmplitude ?? -1).ToString("R"),
                    es.IsNone ? "" : es.PulsePattern!.PulseMode.PulseType.ToString(), es.IsNone ? "" : es.PulsePattern!.PulseMode.PulseCount.ToString(),
                    es.IsNone ? "" : es.PulsePattern!.PulseMode.Alternative.ToString(), carrier,
                    control.Motor.Parameter.Te.ToString("R"), control.Motor.Parameter.Ωr.ToString("R") }));
                for (int i = 0; i < calc; i++)
                {
                    control.AddTimeAll(dt);
                    double v;
                    if (mode == "train") v = CalculateTrainSound(control, train);
                    else { var s = Common.CalculatePhsaseState(control, 0); v = (s.U - s.V) * 0.5; }
                    bw.Write((float)v);
                    t += dt;
                }
            }
        }
        return 0;
    }
}
