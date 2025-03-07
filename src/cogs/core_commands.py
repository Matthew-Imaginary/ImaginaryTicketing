from typing import Union
import logging

import discord
from discord.ext import commands
from discord.utils import get

import cogs.helpers.views.action_views as action_views
from cogs.helpers.views import command_views
import cogs.helpers.actions as actions

from utils.database.db import DatabaseManager as db
from utils.utility import Utility, UI
from utils import exceptions, types

import config

log = logging.getLogger(__name__)

class TicketCommands(commands.Cog):
    """core commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ticket", aliases=["t"])
    @commands.has_role(config.roles['admin'])
    async def ticket(self, ctx: commands.Context):
        """shows a ticket message"""
        bot_commands: discord.TextChannel = get(
            ctx.guild.text_channels, name="bot-commands")
        embed = UI.Embed(title="Ticket System", timestamp=None)
        embed.add_field(name="How do I make a ticket?",
                        value=f"Either react to the message below, or type `$create {{help, submit, misc}}` in {bot_commands.mention}. (Note `$create` defaults to help)")
        embed.add_field(name="Rules", value="""
- Abuse of the ticket system will result in being punished.

For help tickets:
- You must show what you've tried so far before we help you
- Only create one for per challenge
- No points will be deducted
- Cannot be created for the current challenge before either:
\u200b \u200b - 30 minutes have passed since the challenge was released
\u200b \u200b - the challenge has been blooded
""", inline=False)
        await ctx.channel.send(embed=embed, view=command_views.TicketView(self.bot))
        await Utility.delete_message(ctx)

    @commands.command(name="create", aliases=["new", "cr"])
    @commands.cooldown(rate=5, per=10, type=commands.BucketType.default)
    async def create(self, ctx: commands.Context, ticket_type: types.TicketType = "help", member: discord.Member = None):
        """create a new ticket for the user if non-admin, or with the user specified if admin"""
        if ticket_type not in {'help', 'submit', 'misc'}:
            await ctx.channel.send("possible ticket types are help, submit, and misc")
            return
        admin = get(ctx.guild.roles, name=config.roles['admin'])
        if admin not in ctx.author.roles:
            member = ctx.author
            create_ticket = actions.CreateTicket(self.bot,
                                                 ticket_type, None, ctx.guild, member, ctx.channel)
        else:
            if member and member.bot:
                await ctx.channel.send("tickets cannot be created for bots")
                return
            member = member or ctx.author
            create_ticket = actions.CreateTicket(self.bot,
                                                 ticket_type, None, ctx.guild, member, ctx.channel)
        await Utility.delete_message(ctx)
        try:
            await create_ticket.main()
        except (exceptions.MaxUserTicketError, exceptions.MaxChannelTicketError, discord.errors.NotFound):
            pass

    @commands.command(name="add", aliases=["a"], help="add a user to a ticket")
    @commands.has_role(config.roles['admin'])
    async def add(self, ctx, member: discord.Member):
        """adds a user to a ticket"""

        memids = [member.id for member in ctx.channel.members]
        if member.id in memids:
            embed = UI.Embed(
                description=f"User {member.name} already in channel")
            await ctx.channel.send(embed=embed)
            return

        admin = get(ctx.guild.roles, name=config.roles['admin'])
        if admin in member.roles:
            embed = UI.Embed(description=f"User {member.name} is an admin")
            await ctx.channel.send(embed=embed)
            return

        await actions.UtilityActions.add(ctx.channel, member)

    @commands.command(name="remove", aliases=["r", "rm"])
    @commands.has_role(config.roles['admin'])
    async def remove(self, ctx, member: discord.Member):
        """removes a user from a ticket"""

        memids = [member.id for member in ctx.channel.members]
        if member.id not in memids:
            embed = UI.Embed(
                description=f"User {member.name} not in channel")
            await ctx.channel.send(embed=embed)
            return
        admin = get(ctx.guild.roles, name=config.roles['admin'])
        if admin in member.roles:
            embed = UI.Embed(description=f"User {member.name} is an admin")
            await ctx.channel.send(embed=embed)
            return

        await actions.UtilityActions.remove(ctx.channel, member)

    @commands.command(name="close", aliases=["cl"])
    async def close(self, ctx):
        """closes a ticket"""
        try:
            user_id = db.get_user_id(ctx.channel.id)
        except ValueError as e:
            return await ctx.channel.send(e.args[0])
        guild = ctx.guild
        admin = get(guild.roles, name=config.roles['admin'])
        if admin in ctx.author.roles or user_id == ctx.author.id:

            close_ticket = actions.CloseTicket(ctx.guild, ctx.author,
                                               ctx.channel)
            await Utility.delete_message(ctx)
            await close_ticket.main()
        else:
            await ctx.channel.send("You do not have enough permissions to run this command")

    @commands.command(name="delete", aliases=["del"])
    @commands.has_role(config.roles['admin'])
    async def delete(self, ctx):
        """deletes a ticket"""
        delete_ticket = actions.DeleteTicket(ctx.guild, ctx.author,
                                             ctx.channel)
        try:
            await delete_ticket.main()
        except discord.errors.NotFound:
            pass

    @commands.command(name="reopen", aliases=["re", "reo", "re-open"])
    @commands.has_role(config.roles['admin'])
    async def reopen(self, ctx):
        """reopens a ticket"""
        reopen_ticket = actions.ReopenTicket(ctx.guild, ctx.author,
                                             ctx.channel)
        await reopen_ticket.main()

        await Utility.delete_message(ctx)

    @commands.command(name="transcript", aliases=["tsc"])
    @commands.has_role(config.roles['admin'])
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.default)
    async def transcript(self, ctx, destination: Union[discord.User, discord.TextChannel]):
        """sends a transcript to a user via DM"""
        await Utility.transcript(ctx.channel, destination)
        await ctx.channel.send("transcript sent to channel")
        await Utility.delete_message(ctx)

    @commands.command(name="autoclose", aliases=["ac"])
    @commands.has_role(config.roles['admin'])
    async def autoclose(self, ctx, option: str = "off", channel: discord.TextChannel = None):
        """turns the autoclose feature on or off for a give channel"""

        if channel is None:
            channel = ctx.channel
        if option == "off":
            db.update_check("2", channel.id)
            await ctx.channel.send(f"autoclose is now off for {ctx.channel.name}")
        else:
            db.update_check("0", channel.id)
            await ctx.channel.send(f"autoclose is now on for {ctx.channel.name}")

    @commands.command(name="auto_message", aliases=["am"])
    @commands.has_role(config.roles['admin'])
    async def auto_message(self, ctx, channel: discord.TextChannel):
        """Sends a message asking if the ticket can be closed. Does not contribute to AC checks"""
        try:
            user_id = db.get_user_id(channel.id)
        except ValueError as e:
            return await ctx.channel.send(e.args[0])

        member = ctx.guild.get_member(int(user_id))
        message = f"If that is all we can help you with {member.mention}, please close this ticket.\n||I am a bot and this action was performed automatically||"
        random_admin = await Utility.random_admin_member(ctx.guild)
        await Utility.say_in_webhook(self.bot, random_admin, channel, random_admin.avatar.url, True, message, return_message=True, view=action_views.CloseView())

        embed = UI.Embed(
            title="Auto Message", description=f"{random_admin.mention} said the auto close message in {channel.mention}")
        embed.set_author(name=f"{ctx.author}",
                         icon_url=f"{ctx.author.avatar.url}")

        await ctx.channel.send(embed=embed)
        await Utility.delete_message(ctx)

    def cog_check(self, ctx):
        if not ctx.message.guild:
            raise commands.errors.NoPrivateMessage(
                'Command cannot be used in DMs.')
        return True

def setup(bot: commands.Bot):
    bot.add_cog(TicketCommands(bot))
