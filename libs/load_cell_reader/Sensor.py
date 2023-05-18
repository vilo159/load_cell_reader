import datetime
from X_Load import X_Load

class Sensor:

    def __init__(self):
        self.REAL_DATA = True
        self.keys = ["Time","X Load","Y Load","Friction Load","IMU Angle", "Load Cell Height"]
        self.x_load = X_Load()
        self.time = datetime.datetime.now().strftime("%I:%M:%S %p")
        self.sensor_data = {}
        self.cpu_time = 0

    def get_sensor_data(self, adc_out = 0):
        self.sensor_data["X Load"] = round(self.x_load.get_data(adc_out),4)
        return self.sensor_data

    def get_sensor_keys(self):
        return self.keys

# if __name__ == "__main__":
#     sensor = Sensor()
#     print("\n **********Beginning Sensor Test********** \n")
#     print("Sensor Data: ")
#     data_array = sensor.get_sensor_data()
#     for key in sensor.get_sensor_keys():
#         print(key, data_array[key])
#     print("\n **********Ending Sensor Test********** \n")
