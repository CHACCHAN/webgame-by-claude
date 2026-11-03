# VVVF-Simulator reference build (checking the JS port)

`src/game/audio/vvvf/sim.ts` is a line-by-line port of VVVF-Simulator (VvvfGeeks, https://github.com/VvvfGeeks/VVVF-Simulator,
free for non-commercial use). This folder builds the simulator's own non-GUI C# files into a console program that runs
the same calculation along a master-controller scenario, so the port can be compared sample by sample.

- `RefSim.csproj`: compiles the simulator's `Data/`, `Vvvf/` files unchanged (path in `S`), plus
  - `CarrierPatched.cs`: the simulator's `Vvvf/Modulation/Carrier.cs` with `System.Random` replaced by `DetRandom`
    (xorshift32, as `xorshift32` in `audio/vvvf/math.ts`), so the random carrier modulation repeats;
  - `Stubs.cs`: `DetRandom` and an empty stand-in for the Windows-only audio resource loader;
  - `Program.cs`: the real-time frequency control and the in-train sound (copied from `Generation/Audio/…`, which
    need NAudio's Windows parts), writing float32 samples and a trace per control block.
- `scenario-test.txt`: the scenario of the unit test's fixture (`src/game/__tests__/fixtures/vvvf-ref.json`).

```sh
git clone https://github.com/VvvfGeeks/VVVF-Simulator /tmp/vvvf-src
cd frontend/tools/vvvf-ref
docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -e DOTNET_CLI_HOME=/tmp -v "$PWD:/ref" -v /tmp/vvvf-src:/src \
  mcr.microsoft.com/dotnet/sdk:10.0 dotnet build /ref/RefSim.csproj -c Release -p:S=/src/VvvfSimulator/ -o /ref/bin
# RefSim <yaml> <out.f32> <train|line> <scenario> <fs> <calcCount> [gear1 gear2] [seed]
docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -e DOTNET_CLI_HOME=/tmp -v "$PWD/..:/t" -w /t/vvvf-ref \
  mcr.microsoft.com/dotnet/sdk:10.0 dotnet bin/RefSim.dll ../vvvf/JRE_E231_MITSUBISHI.yaml e231.f32 train scenario-test.txt 96000 256 14 99
cd ../.. && npx tsx tools/vvvf-render.ts JRE_E231_MITSUBISHI train tools/vvvf-ref/scenario-test.txt 96000 256 /tmp/e231-js.f32 14 99
# then compare the two float32 files; the fixture (three cases):
# node tools/vvvf-ref/fixture.cjs src/game/__tests__/fixtures/vvvf-ref.json JRE_E231_MITSUBISHI train 14 99 e231.f32 \
#   JRW_207-2000_TOSHIBA_IGBT line 0 0 w207.f32 N1000_SIEMENS_GTO train 14 83 n1000.f32
```

Last check (2026-11-03, simulator commit fb8d0c9): E231 Mitsubishi in-train sound with gear 14:99,
JR West 207-2000 Toshiba line voltage and Keikyu N1000 Siemens GTO in-train sound with gear 14:83 (async
"do-re-mi" start, then CHM 15 … 3 under power and brake: the switching-angle tables), 16.5 s at 96 kHz:
identical in float32; at 192 kHz over 75 s (power, coast, re-power, brake) the largest difference was 6e-11.
`Program.cs` loads the tables (`CustomPwmPresets.Load`) before it starts.
