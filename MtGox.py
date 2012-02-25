from urllib import urlencode
import urllib2
import time
from hashlib import sha512
import hmac
import base64
import json
import datetime

import numpy
from matplotlib import pyplot

class MtGox:
	def __init__( self, api_key, auth_secret, currancy ):
		self.api_key = api_key
		self.auth_secret = auth_secret
		self.currancy = currancy
		self.oldInfo = None
		self.oldOrders = None
		
	def nonce( self ):
		return int( time.time() * 1000000 )
		
	def sign( self, data ):
		return base64.b64encode( str( hmac.new( base64.b64decode( self.auth_secret ), data, sha512).digest() ) )
		
	def build( self, req={} ):
		req["nonce"] = self.nonce()
		post_data = urlencode( req )
		headers = {}
		headers["User-Agent"] 	= "GoxBot"
		headers["Rest-Key"]		= self.api_key
		headers["Rest-Sign"]	= self.sign( post_data )
		
		return (post_data, headers )
	
	def send( self, path, args ):
		try:
			data, headers = self.build( args )
			req = urllib2.Request( "https://mtgox.com/api/0/" + path, data, headers )
			res = urllib2.urlopen( req, data )
			return json.load( res )
		except:
			print "MtGox Timeout"
		
	def getInfo( self ):
		info = self.send( "info.php", {} )
		
		wallet = info['Wallets']
		
		usd_bal = float( wallet['USD']['Balance']['value'] )
		btc_bal = float( wallet['BTC']['Balance']['value'] )
		
		fee_rate = info['Trade_Fee']
		
		return { "usd": usd_bal, "btc": btc_bal, "fee": fee_rate }
		
	def getOrders( self ):
		orders = self.send( "getOrders.php", {} )['orders']
		order = []
		for o in orders:
			status = "active"
			if o['status'] == 0:
				status = "not active"
			elif o['status'] == 2:
				status = "not enough funds"
			
			order.append( { "oid": o['oid'], "type": o['type'], "status": status, "btc_amount": o['amount'], "btc_price": o['price'] } )
			
		return { "orders": order }
		
	def getHighLowAvg( self ):
		try:
			js = self.send( "/data/ticker.php", {} )['ticker']
		
			high = float(js['high'])
			low = float(js['low'])
			avg = float(js['avg'])
			
			percentHigh = 100 * ( high - avg ) / avg
			percentLow = 100 * ( low - avg ) / avg
			self.oldInfo = { "high" : high, "avg": avg, "low" : low, "High%" : percentHigh, "Low%" : percentLow, 'buy': js['buy'], 'sell' : js['sell'], 'vol': js['vol'] }
			return self.oldInfo
		except:
			return self.oldInfo
		
	def graph24h( self ):
		data = self.send( "/data/getTrades.php", {} )
		
		bidDataX = []
		bidDataY = []
		askDataX = []
		askDataY = []
		for o in data:
			if o['trade_type'] == "bid":
				bidDataX.append( float(o['price']) )
				bidDataY.append( o['date'] )
			else:
				askDataX.append( float(o['price']) )
				askDataY.append( o['date'] )
				
		pyplot.plot( bidDataY, bidDataX )
		#pyplot.show()
		pyplot.plot( askDataY, askDataX )
		#pyplot.show()
		
	def getStd( self ):
		data = self.send( "/data/getTrades.php", {} )
		
		bids = []
		asks = []
		
		for o in data:
			if o['trade_type'] == "bid":
				bids.append( float( o['price'] ) )
			else:
				asks.append( float( o['price'] ) )
		
		bidArray = numpy.array( bids )
		askArray = numpy.array( asks )
		
		bidStd = numpy.std( bidArray )
		askStd = numpy.std( askArray )
		
		return ( bidStd, askStd )
		
	def getWeightedAvg( self ):
		data = self.send( "/data/getTrades.php", {} )
		
		bidWeights = []
		askWeights = []
		bids = []
		asks = []
		
		for o in data:
			if o['trade_type'] == "bid":
				bids.append( float( o['price'] ) )
			else:
				asks.append( float( o['price'] ) )
			
		bidTotal = len( bids )
		askTotal = len( asks )
		
		for i in range( bidTotal ):
			bidWeights.append( float( ( i * 1.0 )  / ( 1.0 * bidTotal ) ) )
			
		for i in range( askTotal ):
			askWeights.append( float( ( i * 1.0 ) / ( 1.0 * askTotal ) ) )
			
		bidAvg = numpy.average( bids, weights=bidWeights )
		askAvg = numpy.average( asks, weights=askWeights )
		
		return ( bidAvg, askAvg )
		
	def getBollingerBand( self ):
		stds = self.getStd()
		avg = self.getWeightedAvg()
		prices = self.getHighLowAvg()
		
		upperBid = avg[0] + stds[0] * 2
		lowerBid = avg[0] - stds[0] * 2
		
		upperAsk = avg[0] + stds[0] * 2
		lowerAsk = avg[0] - stds[0] * 2
		
		bidWidth = ( upperBid - lowerBid ) / avg[0]
		askWidth = ( upperAsk - lowerAsk ) / avg[1]
		
		pbBid = ( prices['buy'] - lowerBid ) / ( upperBid - lowerBid )
		pbAsk = ( prices['sell'] - lowerAsk ) / ( upperAsk - lowerAsk )
		
		return { "bid": { "width": bidWidth, "pb": pbBid }, "ask": { "width": askWidth, "pb": pbAsk } }
		
	def placeAsk( self, amount, price ):
		args = {}
		args['amount'] = amount
		args['price'] = price
		args['Currancy'] = self.currancy
		
		self.send( "/sellBTC.php", args )
	
	def placeBid( self, amount, price ):
		args = {}
		args['amount'] = amount
		args['price'] = price
		args['Currancy'] = self.currancy
		
		self.send( "/buyBTC.php", args );
		
	def cancelOrder( self, orderid, type ):		
		args = {}
		args['type'] = type
		args['oid'] = orderid
		
		self.send( "/cancelOrder.php", args )
		
if __name__ == "__main__":
	api_key = "0b476d98-8768-4ab9-a966-772636f8355e"
	secret = "6Aob7YJo7YM6Vfc7WJb4z3HMvBZrDSuEiDSfbEs5e73F1F/Z1OOTgTNuhwNWDEwD2dG69pN08ZzNbQs/roG/6g=="
	currancy = "USD"
	m = MtGox( api_key, secret, currancy )
	
	print "StanderDeviation:",m.getStd()
	print "WeightedAverages:",m.getWeightedAvg()
	print "BollingerBand",m.getBollingerBand()
	
