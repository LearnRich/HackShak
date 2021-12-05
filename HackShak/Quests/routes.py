from flask import Blueprint, render_template, request, url_for, redirect, flash, abort, jsonify
from HackShak import db, __ADMIN_ROLE, __TEACHER_ROLE, __STUDENT_ROLE
from flask_login import current_user, login_required
from HackShak.Users.utils import roles_required
from HackShak.Quests.forms import QuestForm, SubmissionForm, SubmissionReviewForm
from HackShak.Quests.utils import get_allowed_tags
from HackShak.models import Quest, QuestSubmission, SubmissionStatus, Student, SubmissionFeedback, Campaign
from HackShak.schemas import QuestSchema
from bleach import clean, sanitizer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_



quests = Blueprint('quests', __name__)

# |------------------------------------------|
# | Routes related to individual quest pages |
# |------------------------------------------|

@quests.route('/quest/<int:quest_id>/')
@login_required
def quest(quest_id):
	#if the quest exists as a submission for a student 
	quest = Quest.query.get_or_404(quest_id)
	return render_template('quest.html', title=quest.title, quest=quest, legend='Quest')

@quests.route('/quest/submission/start/<int:quest_id>')
@login_required
def quest_submission_start(quest_id):
	# check if the student has already started working on this 
	submission = QuestSubmission.query.filter_by().first()
	if submission == None:

		submission = QuestSubmission(studentid=current_user.id, course_id=current_user.get_role_obj().get_current_enrolled_course(), quest_id=quest_id)
		db.session.add(submission)
		db.commit()
	
	# if it does not exist create a new one
	return redirect(url_for('quests.quest_submission', submission_id=submission.id))

@quests.route('/quest/submission/<int:submission_id>/', methods=['GET','POST'])
@login_required
def quest_submission(submission_id):
	# get existing student work 
	submission = QuestSubmission.query.get_or_404(submission_id)
	if submission.student_id != current_user.id:
		abort(403)
	form = SubmissionForm()
	if form.validate_on_submit():
		submission.submission_text = form.submission_text.data
		db.session.commit()
		flash('Your announcement has been updated!', 'success')
		return redirect(url_for('quests.quest_submission', submission_id=submission.id))
	elif request.method == 'GET':
		form.submission_text.data = submission.submission_text
	return render_template('quest_submission.html', submission=submission, form=form, legend='Quest Submission')

@quests.route('/quest/submission/<int:submission_id>/review', methods=['GET','POST'])
@login_required
@roles_required([__TEACHER_ROLE])
def quest_submission_review(submission_id):
	# get attached file(s)
	submission = QuestSubmission.query.get_or_404(submission_id)
	print(submission.feedback)
	form = SubmissionReviewForm()
	if form.validate_on_submit():
		feedback = SubmissionFeedback(
			submission_id=submission.id,
			teacher_id=current_user.id,
			feedback_text=form.feedback_text.data
		)
		submission.awarded_xp = form.awarded_xp.data
		submission.feedback.append(feedback)
		submission.status = SubmissionStatus.RETURNED
		db.session.commit()
		flash('Submission has been returned to student.', 'success')
		return redirect(url_for('quests.quest_submission_review', submission_id=submission.id))
	return render_template('quest_submission_review.html', submission=submission, form=form, legend='Review Quest Submission')

@quests.route('/quest/submission/<int:submission_id>/feedback/remove', methods=['GET','POST'])
@login_required
@roles_required([__TEACHER_ROLE])
def feedback_remove(submission_id):
	feedback = SubmissionFeedback.query.get_or_404( request.form['hidden_input'])
	db.session.delete(feedback)
	db.session.commit()
	flash("Your feedback has been deleted.")
	return redirect(url_for('quests.quest_submission_review', submission_id=submission_id))
	

@quests.route('/quest/create', methods=['GET','POST'])
@login_required
@roles_required([__ADMIN_ROLE, __TEACHER_ROLE])
def quest_create():
	form = QuestForm()
	if form.validate_on_submit():
		campaign = Campaign.query.get(form.campaign.data)
		# title, description, xp, campaign, repeatable, expiry, details, submission_instructions, quest_author

		quest = Quest()
		quest.title = form.title.data
		quest.description = form.description.data
		quest.details = form.details.data
		quest.submission_instructions = form.submission_instructions.data
		quest.xp = form.xp.data
		quest.repeatable = form.repeatable.data
		quest.author_id = current_user.id
		quest.campaign = campaign

		db.session.add(quest)
		db.session.commit()

		flash('You Quest has been created and shared', 'success')
		return redirect(url_for('quests.quest', quest_id=quest.id))
	return render_template('quest_create.html', form=form, title='New Quest', legend='New Quest')
	


@quests.route('/quest/<int:quest_id>/update/', methods=['GET','POST'])
@login_required
@roles_required([__ADMIN_ROLE, __TEACHER_ROLE])
def quest_update(quest_id):
	quest = Quest.query.get_or_404(quest_id)
	form = QuestForm()
	if form.validate_on_submit():
		quest.title = form.title.data
		quest.description = form.description.data
		quest.xp = form.xp.data
		quest.repeatable = form.repeatable.data
		quest.expirt = form.expiry.data
		quest.details = form.details.data
		quest.submission_instructions = form.submission_instructions.data 

		quest_campaign = Campaign.query.get(form.campaign.data)
		quest.campaign = quest_campaign

		print(quest.campaign)

		db.session.commit()
		flash('Your quest has been updated!', 'success')
		print("Quest Update:", quest)
		return redirect(url_for('quests.quest', quest_id=quest.id))
	elif request.method == 'GET':
		form.title.data = quest.title
		form.description.data = quest.description
		form.xp.data = quest.xp
		if quest.campaign:
			form.campaign.choices = [(quest.campaign.id, quest.campaign.name)]
			form.campaign.default = quest.campaign.id
		form.repeatable.data = quest.repeatable
		form.expiry.data = quest.expiry
		form.details.data = quest.details
		form.submission_instructions.data = quest.submission_instructions
	else:
		print("The Quest form is not valid")
	return render_template('quest_create.html', title='Update Quest', quest=quest, form=form, legend='Update Quest')

@quests.route('/quest/<int:quest_id>/delete/', methods=['POST'])
@login_required
@roles_required([__ADMIN_ROLE, __TEACHER_ROLE])
def quest_delete(quest_id):
	quest = Quest.query.get_or_404(quest_id)
	try:
		db.session.delete(quest)
		db.session.commit()
		flash('Your quest has been deleted.', 'message')
	except IntegrityError  as e:
		flash('You are attempting to do something to the database that you are not allowed', 'warning')	
		next_page = request.args.get('next')
		return redirect(next_page) if next_page else redirect(url_for('quests.quests_all'))
	return redirect(url_for('quests.quests_all'))

# |------------------------------------|
# | Routes related to quest list pages |
# |------------------------------------|

@quests.route('/quests/map/')
@login_required
def quests_maps():
	return redirect(url_for('main.home'))

@quests.route('/quests/all')
@login_required
def quests_all():
	page = request.args.get('page', 1, type=int)
	quests = Quest.query.paginate(page=page, per_page=20)
	return render_template('quests-all.html', quests=quests)

@quests.route('/quests/available/')
@login_required
@roles_required([__STUDENT_ROLE])
def quest_available():
	student = Student.query.get_or_404(current_user.id)
	# ARGG THIS ONE IS HARD.
	# Get Submitted submission
	# Get Completed Submission
	# check course maps for where quest submissions have been met
	# Then get next quest
	return redirect(url_for('quests.quests_all'))

@quests.route('/quests/inprogress/')
@login_required
@roles_required([__STUDENT_ROLE])
def quest_inprogress():
	student = Student.query.get_or_404(current_user.id)
	in_progress = student.submissions.filter_by(status=SubmissionStatus.IN_PROGRESS)
	# also need to double check for current course/term
	return redirect(url_for('quests.quests_all'))

@quests.route('/quests/completed/')
@login_required
@roles_required([__STUDENT_ROLE])
def quest_completed():
	student = Student.query.get_or_404(current_user.id)
	# also need to filter for current course/term
	completed = student.submissions.filter(QuestSubmission.status.in_([SubmissionStatus.RETURNED, SubmissionStatus.SUBMITTED]))
	return redirect(url_for('quests.quests_all'))

@quests.route('/quests/pastcourses/')
@login_required
@roles_required([__STUDENT_ROLE])
def quest_past():
	student = Student.query.get_or_404(current_user.id)
	# Filter by course not in current term
	completed = student.submissions.filter_by(status=SubmissionStatus.RETURNED)
	return redirect(url_for('quests.quests_all'))

# |------------------------------------|
# | Routes related to quest AJAX Calls |
# |------------------------------------|

@quests.route('/quests/search/', defaults={'limit':None}, methods=['POST'])
@quests.route('/quests/search/<int:limit>', methods=['POST'])
@login_required
@roles_required([__TEACHER_ROLE])
def quests_search(limit):
	json_quest_list = []
	if request.method == 'POST':
		quest_name_qry = request.form['query']
		
		if limit:
			quests = Quest.query.filter(Quest.title.contains(quest_name_qry)).limit(limit).all()
		else:
			quests = Quest.query.filter(Quest.title.contains(quest_name_qry)).all()

		quest_schema = QuestSchema()
		for quest in quests:
			output = quest_schema.dump(quest)
			json_quest_list.append(output)

	return jsonify({
		'search_results':json_quest_list
		})
