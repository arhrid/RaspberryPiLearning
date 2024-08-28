#!/usr/bin/env python3, gpiozero, RPi.GPIO
# Filename    : BuildingManagementSystem.py
# Description : Ambient light control, Room temperature, Fire alarm system, Security System
# modification: 2024/06/11

#Use the PIR sensor to turn on green LED when motion is detected.
#Turn off Green LED if no motion is detected for 10 seconds.

#Use DHT-11 sensor to calculate temperature every second,
#and take average of readings from last three seconds.
#Acquire HUMIDITY from CIMIS csv file.
#weatherIndex = temperature + 0.05 * humidity

#User can set the desired_temp using two pushbuttons.
#Turn on AC if weatherIndex > 3 + desired_temp (represented by RED LED)
#Turn on heater if weatherIndex < desired_temp - 3 (represented by BLUE LED)
#If the doors or windows are open, turn the HVAC off.
#Display weather index, the desired temperature and the HVAC status (off/AC/heat) on the LCD
#Whenever an action takes place (ex. "AC is on"), erase the LCD and display a message
#explaining the action for 3 seconds. Display should go back to normal after 3 seconds.

#A push button represents the door and window using one pushbutton for both.
#When the button is pressed, the door/window status changes, display a warning message such as “door/window open!” or ”door/window closed!” on
#the entire LCD for 3 seconds. HVAC is off while the door/window is open.
#door/window status displayed as open/closed on the LCD.

#import statements
from gpiozero import LED, Button, PWMLED, MotionSensor

import RPi.GPIO as GPIO
import time
import requests

import pytz
import json

import smbus
from time import sleep, strftime
from datetime import datetime
from LCD1602 import CharLCD1602
import adafruit_dht
import board

#initialize DHT11 device, pin Numbers, and other sensors
dht_sensor = adafruit_dht.DHT11(board.D13)
display_lcd = CharLCD1602()
current_humidity = 52 # 52% humidity, change later to obtain value from CIMIS data retriveal

lights_pin = 21       # define lights_pin (green LED) for GPIO 21 (pin number 40)
motion_pin = 5 # define motion_pin (represented by PIR sensor) for GPIO 5 (pin number 29)

air_conditioning_pin = 12    # define air_conditioning_pin (blue LED) for GPIO 12 (pin number 32)
heater_pin = 16    # define heater_pin (red LED) for GPIO 16 (pin number 36)

door_window_pin = 18    # define door_window_pin (represented by yellow push button) for GPIO 18 (pin number 12)

increase_temp_pin = 20    # define increase_temp_pin (represented by green push button) for GPIO 20 (pin number 38)
decrease_temp_pin = 25    # define decrease_temp_pin (represented by red push button) for GPIO 25 (pin number 22)

temp_pin = 17    # define temp_pin (DHT11) for GPIO 17 (pin number 11), use BOARD for this one

desired_temp =  69 #user can increase or decrease the desired temperature by pressing
                        #increase_btn or decrease_btn
average_temp = 69
#set starting values for the HVAC system and temperature readings displayed
door_window_status = 'C'
hvac_status = "HEAT" #possible values HEAT, AC, OFF
lights_status = "OFF"
weather_index = 75
air_conditioning_status = 0 #0 for off, 1 for on
heater_status = 0 #0 for off, 1 for on
default_temp = 75
default_humidity = 50
first_temp, second_temp, third_temp = 74, 74, 74

air_conditioning_led = LED(air_conditioning_pin)
heater_led = LED(heater_pin)
door_window_btn = Button(door_window_pin)
increase_btn = Button(increase_temp_pin)
decrease_btn = Button(decrease_temp_pin)
#we are using PWMLED for the fire alarm system and for motion detection
lights_pwm = PWMLED(lights_pin ,initial_value=0 ,frequency=1)
#the period is 1/1 = 1 second and the duty cycle varies from 0 to 0.5 to 1 throughout the program
air_conditioning_led.off()
heater_led.off()
display_lcd.init_lcd()

pir_sensor = MotionSensor(motion_pin)
pir_sensor.wait_for_no_motion()

fire_status = 0

def print_main_screen():
    global desired_temp, average_temp, door_window_status, hvac_status, lights_status, weather_index
    display_lcd.clear()
    display_lcd.write(0,0, str(desired_temp) + '/' + str(weather_index))
    display_lcd.write(12,0,'Dr:' + str(door_window_status))

    display_lcd.write(0,1,'H:' + str(hvac_status))
    display_lcd.write(11,1,'L:' + str(lights_status))

def startup():
    heater_led.off()
    air_conditioning_led.off()
    print_main_screen()

def repeat():
    pir_current_detection = False
    pir_earlier_detection = False
    global desired_temp, average_temp, door_window_status, hvac_status, lights_status, current_humidity, temp_pin, weather_index
    global air_conditioning_status, heater_status, first_temp, second_temp, third_temp, fire_status
    air_conditioning_led.off()
    heater_led.off()

    print('Initial Weather index is ' + str(weather_index) + " %")
    print('Initial Average temperature is ' + str(average_temp) + " F")
    print('Initial Desired temperature is ' + str(desired_temp) + " F\n")

    try:
        # Display the temperature on the terminal
        first_temp = (int)(round(dht_sensor.temperature * (9 / 5) + 32))
        print("First Temp: {:d} F ".format(first_temp))
    except:
        #message if temperature could not be properly received.
        print("DHT-11 provided invalid readings. Proceed to the next round.")
        first_temp = default_temp
        time.sleep(2.0)
    time.sleep(1)

    try:
        # Display the temperature on the terminal
        second_temp = (int)(round(dht_sensor.temperature * (9 / 5) + 32))
        print("Second Temp: {:d} F ".format(second_temp))
    except:
        #message if temperature could not be properly received.
        print("DHT-11 provided invalid readings. Proceed to the next round.")
        second_temp = default_temp
        time.sleep(2.0)
    time.sleep(1)
    while True:
        print("Air conditioning status is " + str(air_conditioning_status))
        print("Heater status is " +str(heater_status))

        if(door_window_btn.is_pressed):
            hvac_msg = 'ON' #change depending on whether door/window is open or closed now
            print('\nDoor/window button has been pressed.')
            if (door_window_status == 'C'):
                door_window_status = 'O'
                hvac_msg = 'HALTED'
                hvac_status = 'OFF'
            else:
                door_window_status = 'C'
                hvac_status  = 'AC' #change to not be 'OFF', will result to accurate value later
            display_lcd.clear()
            display_lcd.write(2,0,'Window/Door ' + str(door_window_status))
            display_lcd.write(3,1,'HVAC ' + str(hvac_msg))
            time.sleep(3) #dispplay warning message on entire LCD for 3 seconds
            print_main_screen()

        pir_current_detection = pir_sensor.motion_detected
        # If the sensor is triggered
        while (pir_current_detection == True and pir_earlier_detection == False and fire_status != 1):
            lights_pwm.value = 1
            lights_status = 'ON'
            print('Motion detected. Lights turned off after 10 seconds of no motion.')
            # Record previous state
            print_main_screen()
            sleep(10)
            lights_pwm.value = 0
            lights_status = 'OFF'
            pir_earlier_detection = True
            print_main_screen()
            print("pir_earlier_detection is" + str(pir_earlier_detection))

        #Either motion is sensed again and the led turns on once more
        #or the led turns off after 10 seconds of no motion
        # Ready state refers to no motion so the led (represented by pwm) is turned off by having a duty cycle of 0
        if (pir_current_detection == False and pir_earlier_detection == True and fire_status != 1):
            lights_pwm.value = 0
            print('Lights off and ready state is returned to.')
            pir_earlier_detection = False
            lights_status = 'OFF'
            print_main_screen() #display LCD main screen
            print("pir_earlier_detection is" + str(pir_earlier_detection))

        if hvac_status != 'OFF':
            try:
                # Display the temperature on the terminal
                third_temp = (int)(round(dht_sensor.temperature * (9 / 5) + 32))
                print("Most recent Temp: {:d} F    Humidity: {:d} % ".format(third_temp,dht_sensor.humidity))
                backup_humidity = (int)(round(dht_sensor.humidity))
            except:
                #message if temperature could not be properly received.
                print("DHT-11 provided invalid readings. Proceed to the next round.")
                third_temp = default_temp
                time.sleep(2.0)
            time.sleep(1)

            average_temp = (int) (round ((first_temp + second_temp + third_temp) / 3.0 ))

            print('The average temperature of the previous 3 readings is ' + str(average_temp) + " F")

            stationNum = 75 #for Irvine weather station data

            losAngelesTz = pytz.timezone('America/Los_Angeles')
            irvineTime = datetime.now(losAngelesTz)
            monthStr = str(irvineTime.month)
            dayStr = str(irvineTime.day)
            print(irvineTime.strftime('%a %d %b %Y, %I:%M%p'))
            #get today's date and acquire the hour near Irvine, CA (Pacific time zone)
            if (irvineTime.month < 10):
                monthStr = "0" + str(irvineTime.month)
            if (irvineTime.day < 10):
                dayStr = "0" + str(irvineTime.day)
            dateStr = str(irvineTime.year) + "-" + monthStr +"-" + dayStr
            base_url = 'http://et.water.ca.gov/api/data?appKey=7f0afd98-ad50-43c6-a689-dafa276ba0d9&targets=' + str(stationNum) +'&startDate=' + dateStr + '&endDate=' + dateStr + '&dataItems=hly-rel-hum'
            print(dateStr)
            print(base_url + "\n")
            #based on the hour extract the

            print("The current hour is " + str(irvineTime.hour) + "\n") #returns a value from 0 to 23
            if(irvineTime.hour <= 2):
                #use backup humidity
                current_humidity = backup_humidity
            else:
                try:
                    response = requests.get(base_url)
                    #print(response.text)
                    if response.status_code == 200:
                        # Convert the response to JSON format
                        posts = response.json()
                #just the values from the json formatted data
                        extra_formatted_posts = json.dumps(posts.get("Data").get("Providers")[0].get("Records")[irvineTime.hour - 3: irvineTime.hour], indent = 4, sort_keys=True)
                        print(extra_formatted_posts)
                        #print(extra_formatted_posts)
                        print(posts.get("Data").get("Providers")[0].get("Records")[irvineTime.hour - 3].get("Hour"))
                        current_humidity = (int)(posts.get("Data").get("Providers")[0].get("Records")[irvineTime.hour - 3].get("HlyRelHum").get("Value"))
                    else:
                        print("Failed to retrieve data.")
                        current_humidity = backup_humidity
                    print("Response status code is " + str(response.status_code))
                except:
                    current_humidity = backup_humidity
                    print("Connection issues in retriving CIMIS data. Backup value for humidity acquired by DHT-11 sensor")
            if(current_humidity  == 0):
                current_humidity = 50
            print("Average temp is " + str(average_temp))
            print("The current humidity is " + str(current_humidity) + "%")

            weather_index = (int)(round(average_temp + current_humidity*0.05))
            print("The weather index is " + str(weather_index))
            print_main_screen()
            first_temp = second_temp + 0
            second_temp = third_temp + 0

        #implement heater and air conditioning functionality
        #air_conditioning_status and heater_status reveal whether they have been turned on before, no need to keep displaying message
        if ((weather_index > desired_temp + 3) and (air_conditioning_status == 0) and (door_window_status != 'O')):
            air_conditioning_status = 1
            print("Air conditioning status is " + str(air_conditioning_status))
            air_conditioning_led.on()
            heater_led.off()
            hvac_status = 'AC'

            display_lcd.clear()
            display_lcd.write(6,0,'AC is')
            display_lcd.write(7,1,'ON')
            time.sleep(3) #return to normal display after 3 seconds
            print_main_screen()
        if (( weather_index < desired_temp - 3) and (heater_status == 0) and (door_window_status != 'O')):
            heater_status = 1
            print("Heater status is " +str(heater_status))
            air_conditioning_led.off()
            heater_led.on()
            hvac_status = 'HEAT'

            display_lcd.clear()

            display_lcd.write(4,0,'Heater is')

            display_lcd.write(7,1,'ON')
            time.sleep(3) #return to normal display after 3 seconds
            print_main_screen()

        if((weather_index >= desired_temp - 3) and (weather_index <= desired_temp + 3)):
            air_conditioning_status = 0
            heater_status = 0
            heater_led.off()
            air_conditioning_led.off()
            hvac_status = 'OFF'

        #display emergency message in fire scenario
        if (weather_index > 95):
            fire_status = 1
            door_window_status = 'O'
            lights_pwm.value = 0.5 #duty cycle is 50% with a a preset period of 1 second
            display_lcd.begin(16,2)     # set number of LCD lines and columns
            display_lcd.clear()
            display_lcd.write(0,0,'FIRE, EVAC! Dr:O\n')
            display_lcd.write(0,1,'HVAC OFF')
            time.sleep(3)
            heater_led.off()
            air_conditioning_led.off()
            hvac_status = 'OFF'
        else:
            fire_status = 0
            lights_pwm.value = 0
            if(hvac_status != 'AC' and hvac_status != 'HEAT'):
                hvac_status = 'OFF' # placeholder value until next round of LCD updates

        print('The desired temperature is currently ', desired_temp)
        if(increase_btn.is_pressed): #for an output, false for a LOW value (button pressed)
            print('\nIncrease button has been pressed.')
            desired_temp += 1
            print(desired_temp)
            if desired_temp > 95: #rolls over to value 65 if desired_temp exceeds 95
                desired_temp = 65
            print_main_screen()
            time.sleep(0.5)
            print('The updated desired temperature is ', desired_temp, '\n')

        if(decrease_btn.is_pressed): #for an output, false for a LOW value (button pressed)
            print('\nDecrease button pin has been pressed.')
            desired_temp -= 1
            print(desired_temp)
            if desired_temp < 65: #rolls over to value 95 if desired_temp is below 65
                desired_temp = 95
            print_main_screen()
            time.sleep(0.5)
            print('The updated desired temperature is ', desired_temp, '\n')

        print("First Temp: {:d} F ".format(first_temp))
        print("Second Temp: {:d} F".format(second_temp))
        print("HVAC: " + str(hvac_status) + " Lights: " +str(lights_status) + " Doors: " + str(door_window_status))

if __name__ == '__main__':     # Program entrance
    print ('HVAC Simulator with DHT11, Infrared Sensor, LCD, LEDs, and Pushbuttons...')
    startup() #setup inputs and outputs
    try:
        repeat() #continue LCD, LED, DHT, Infrared Sensor functionality until KeyboardInterrupt
    except KeyboardInterrupt:  # program ends with ctrl c
        air_conditioning_led.off() #turn off Leds, PWMLeds, sensor, and display_lcd
        heater_led.off()
        lights_pwm.close()
        pir_sensor.close()
        display_lcd.clear()
        GPIO.cleanup()                     # Release GPIO resources
        exit()
