# Rolltide

Functional language compiler prototype for embedded systems that require repeatable tasks. Particularly designed for robotics applications even though I am no longer involved in robotics. Oh well.

## How to Use

Don't look into it too closely.   

```
struct PID
  p: i32
  i: i32
  d: i32

  error: signal f32
  @private dt: f32
  @private previous_error: f32
  @private integral: f32

  @private previous_errors: mut array[f32, 10]

into PID
  def new [p: i32, i: i32, d: i32] =
    PID with
      p, i, d
      error = signal 0.0
      dt = 0.0
      previous_error =  0.0
      integral = 0.0
      previous_errors = mut array[f32, 10] of 0.0
  
  def start [self: PID] =
    when self.error
      value i32 =
        self.previous_errors.push self.error.value as f32
        if self.previous_errors.len > 10
          self.previous_errors.pop_front
        self.p + self.i + self.d
    
  def update [self: PID, setpoint: signal f32, measurement: signal f32, dt: signal f32] =
    self.dt = dt
    self.error = setpoint - measurement # dispatches to signal listeners through assignment, updates signal value
    self.integral += self.error * dt
    derivative = (self.error - self.previous_error) / dt
    self.previous_error = self.error
    output = (self.p as f32) * self.error + (self.i as f32) * self.integral + (self.d as f32) * derivative
    output as i32

into PID fulfills Default
  def default() =
    PID.new 1, 0, 0

into PID fulfills Show
  def fmt [self: PID, f: &mut Formatter] =
    f.write_str "PID Controller"
    f.write_str ("(P: {}, I: {}, D: {})".format self.p, self.i, self.d)
```