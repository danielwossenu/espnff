import requests

from .utils import (two_step_dominance,
                    power_points, )


class ESPNFFException(Exception):
    pass


class PrivateLeagueException(ESPNFFException):
    pass


class InvalidLeagueException(ESPNFFException):
    pass


class UnknownLeagueException(ESPNFFException):
    pass


class League(object):
    '''Creates a League instance for Public ESPN league'''
    def __init__(self, league_id, year):
        self.league_id = league_id
        self.year = year
        self.ENDPOINT = "http://games.espn.com/ffl/api/v2/"
        self.teams = []
        self._fetch_league()

    def __repr__(self):
        return 'League(%s, %s)' % (self.league_id, self.year, )

    def _fetch_league(self):
        params = {
            'leagueId': self.league_id,
            'seasonId': self.year
        }
        r = requests.get('%sleagueSettings' % (self.ENDPOINT, ), params=params)
        self.status = r.status_code
        data = r.json()

        if self.status == 401:
            raise PrivateLeagueException(data['error'][0]['message'])

        elif self.status == 404:
            raise InvalidLeagueException(data['error'][0]['message'])

        elif self.status != 200:
            raise UnknownLeagueException('Unknown %s Error' % self.status)

        self._fetch_teams(data)

    def _fetch_teams(self, data):
        '''Fetch teams in league'''
        teams = data['leaguesettings']['teams']

        for team in teams:
            self.teams.append(Team(teams[team]))

        # replace opponentIds in schedule with team instances
        for team in self.teams:
            for week, matchup in enumerate(team.schedule):
                for opponent in self.teams:
                    if matchup == opponent.team_id:
                        team.schedule[week] = opponent

        # calculate margin of victory
        for team in self.teams:
            for week, opponent in enumerate(team.schedule):
                mov = team.scores[week] - opponent.scores[week]
                team.mov.append(mov)

        # sort by team ID
        self.teams = sorted(self.teams, key=lambda x: x.team_id, reverse=False)

    def power_rankings(self, week):
        '''Return power rankings for any week'''

        # calculate win for every week
        win_matrix = []
        teams_sorted = sorted(self.teams, key=lambda x: x.team_id,
                              reverse=False)

        for team in teams_sorted:
            wins = [0]*32
            for mov, opponent in zip(team.mov[:week], team.schedule[:week]):
                opp = int(opponent.team_id)-1
                if mov > 0:
                    wins[opp] += 1
            win_matrix.append(wins)
        dominance_matrix = two_step_dominance(win_matrix)
        power_rank = power_points(dominance_matrix, teams_sorted, week)
        return power_rank

    def scoreboard(self, week=None):
        '''Returns list of matchups for a given week'''
        params = {
            'leagueId': self.league_id,
            'seasonId': self.year
        }
        if week is not None:
            params['matchupPeriodId'] = week

        r = requests.get('%sscoreboard' % (self.ENDPOINT, ), params=params)
        self.status = r.status_code
        data = r.json()

        if self.status == 401:
            raise PrivateLeagueException(data['error'][0]['message'])

        elif self.status == 404:
            raise InvalidLeagueException(data['error'][0]['message'])

        elif self.status != 200:
            raise UnknownLeagueException('Unknown %s Error' % self.status)

        matchups = data['scoreboard']['matchups']
        result = [Matchup(matchup) for matchup in matchups]

        for team in self.teams:
            for matchup in result:
                if matchup.home_team == team.team_id:
                    matchup.home_team = team
                if matchup.away_team == team.team_id:
                    matchup.away_team = team

        return result
      
    def schedule_for_sim(self):
      schedule = []
      for week in range(1,data['leaguesettings']['finalRegularSeasonMatchupPeriodId']+1):
        for each in self.scoreboard(week):
          schedule.append([str(each.home_team.owner),str(each.away_team.owner),each.home_score,each.away_score, week])
      return schedule


class Team(object):
    '''Teams are part of the league'''
    def __init__(self, data):
        self.team_id = data['teamId']
        self.team_abbrev = data['teamAbbrev']
        self.team_name = "%s %s" % (data['teamLocation'], data['teamNickname'])
        self.division_id = data['division']['divisionId']
        self.division_name = data['division']['divisionName']
        self.wins = data['record']['overallWins']
        self.losses = data['record']['overallLosses']
        self.points_for = data['record']['pointsFor']
        self.points_against = data['record']['pointsAgainst']
        self.owner = "%s %s" % (data['owners'][0]['firstName'],
                                data['owners'][0]['lastName'])
        self.schedule = []
        self.scores = []
        self.mov = []
        self._fetch_schedule(data)

    def __repr__(self):
        return 'Team(%s)' % (self.team_name, )

    def _fetch_schedule(self, data):
        '''Fetch schedule and scores for team'''
        matchups = data['scheduleItems']

        for matchup in matchups:
            if not matchup['matchups'][0]['isBye']:
                if matchup['matchups'][0]['awayTeamId'] == self.team_id:
                    score = matchup['matchups'][0]['awayTeamScores'][0]
                    opponentId = matchup['matchups'][0]['homeTeamId']
                else:
                    score = matchup['matchups'][0]['homeTeamScores'][0]
                    opponentId = matchup['matchups'][0]['awayTeamId']
            else:
                score = matchup['matchups'][0]['homeTeamScores'][0]
                opponentId = matchup['matchups'][0]['homeTeamId']

            self.scores.append(score)
            self.schedule.append(opponentId)


class Matchup(object):
    '''Creates Matchup instance'''
    def __init__(self, data):
        self.data = data
        self._fetch_matchup_info()

    def __repr__(self):
        return 'Matchup(%s, %s)' % (self.home_team, self.away_team, )

    def _fetch_matchup_info(self):
        '''Fetch info for matchup'''
        if self.data['teams'][0]['home'] and not self.data['bye']:
            self.home_team = self.data['teams'][0]['teamId']
            self.home_score = self.data['teams'][0]['score']
            self.away_team = self.data['teams'][1]['teamId']
            self.away_score = self.data['teams'][1]['score']
        elif self.data['teams'][0]['home'] and not self.data['bye']:
            self.home_team = self.data['teams'][1]['teamId']
            self.home_score = self.data['teams'][1]['score']
            self.away_team = self.data['teams'][0]['teamId']
            self.away_score = self.data['teams'][0]['score']
        else:
            self.home_team = self.data['teams'][0]['teamId']
            self.home_score = self.data['teams'][0]['score']
            self.away_team = None
            self.away_score = None
