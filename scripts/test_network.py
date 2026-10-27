#!/usr/bin/env python3
"""Run: python3 -m unittest discover -s scripts -p 'test_network.py'"""
import unittest
from build_network import build
class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.stops={"stops":[{"id":k,"name":k,"lat":33+i/100,"lon":-79} for i,k in enumerate("ABCD")]}
        self.journeys={"source":"fixture","calendar":[],"trips":[
            {"id":"T1","route":"R1","service":"W","direction":"0","stops":[
                {"stop":"A","seq":1,"dep":"09:00:00","arr":"09:00:00"},
                {"stop":"B","seq":2,"dep":"09:10:00","arr":"09:10:00"},
                {"stop":"C","seq":3,"dep":"","arr":""}]},
            {"id":"T2","route":"R2","service":"W","direction":"1","stops":[
                {"stop":"C","seq":1,"dep":"09:20:00","arr":"09:20:00"},
                {"stop":"D","seq":2,"dep":"09:30:00","arr":"09:30:00"}]}]}
    def test_direction_and_unknown_times(self):
        g=build(self.stops,self.journeys)
        self.assertEqual([e["to"] for e in g["edges"]["A"]],["B"])
        self.assertEqual([e["to"] for e in g["edges"]["B"]],["C"])
        self.assertFalse(g["edges"]["B"][0]["times_complete"])
        self.assertEqual(g["edges"]["C"][0]["route"],"R2")
        self.assertEqual(len(g["nodes"]),4)
    def test_unknown_stop_rejected(self):
        self.journeys["trips"][0]["stops"][0]["stop"]="MISSING"
        with self.assertRaises(ValueError):build(self.stops,self.journeys)
    def test_duplicate_stop_rejected(self):
        self.stops["stops"].append(self.stops["stops"][0])
        with self.assertRaises(ValueError):build(self.stops,self.journeys)
    def test_invalid_coordinates_rejected(self):
        self.stops["stops"][0]["lat"]=100
        with self.assertRaises(ValueError):build(self.stops,self.journeys)
if __name__=="__main__":unittest.main()
